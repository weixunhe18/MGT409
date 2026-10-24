"""Gmail connector tests with fake IMAP/SMTP servers. No network, no key, nothing is ever sent."""

import copy
import unittest
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email import message_from_bytes, policy as email_policy

from supplier_agent.mailbox import GmailMailbox, MailboxConfig, build_reply, to_event
from tests.test_pipeline import make

GMAIL = "weideals25@gmail.com"
TA = "ta.person@yale.edu"


def raw_mail(*, sender=f"TA Person <{TA}>", subject="TB-1 question", body="What is the maximum gate vestige?",
             msgid="<q1@mail.yale.edu>", in_reply_to=None, references=None, auth="dkim=pass header.i=@yale.edu; "
             "spf=pass; dmarc=pass (p=NONE) header.from=yale.edu", extra=None) -> bytes:
    msg = EmailMessage()
    if auth is not None:
        msg["Authentication-Results"] = f"mx.google.com; {auth}"
    msg["From"] = sender
    msg["To"] = f"John <{GMAIL}>"
    msg["Subject"] = subject
    msg["Message-ID"] = msgid
    msg["Date"] = "Sat, 24 Oct 2026 22:10:00 -0400"
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references
    for key, value in (extra or {}).items():
        msg[key] = value
    msg.set_content(body)
    return msg.as_bytes()


def imap_date(dt: datetime) -> bytes:
    return dt.strftime('"%d-%b-%Y %H:%M:%S +0000"').encode()


class FakeIMAP:
    """Speaks the UID commands the connector uses. Messages arrive 'now' unless an arrival time is given."""

    def __init__(self, messages):
        self.messages, self.arrived, self.seen = {}, {}, set()
        for m in messages:
            self.add(m)

    def add(self, raw, arrived=None):
        uid = str(len(self.messages) + 1).encode()
        self.messages[uid] = raw
        self.arrived[uid] = arrived or datetime.now(timezone.utc)
        return uid

    def login(self, user, password):
        return "OK", [b""]

    def select(self, box):
        return "OK", [b""]

    def uid(self, command, *args):
        if command == "SEARCH":
            return "OK", [b" ".join(u for u in self.messages if u not in self.seen)]
        if command == "FETCH":
            uid, what = args
            if "INTERNALDATE" in what:
                return "OK", [b"1 (UID " + uid + b" INTERNALDATE " + imap_date(self.arrived[uid]) + b")"]
            return "OK", [(b"1 (UID " + uid + b" BODY[] {n}", self.messages[uid]), b")"]
        if command == "STORE":
            self.seen.add(args[0])
            return "OK", [b""]
        raise AssertionError(command)

    def logout(self):
        pass


class FakeSMTP:
    def __init__(self):
        self.sent = []

    def login(self, user, password):
        pass

    def send_message(self, msg, from_addr=None, to_addrs=None):
        self.sent.append((msg, to_addrs))

    def quit(self):
        pass


def connect(messages, send_mode="dry-run", **cfg):
    pipeline, store = make()
    box_cfg = MailboxConfig(address=GMAIL, app_password="x", send_mode=send_mode, extra_allow=["@yale.edu"], **cfg)
    pipeline.mailbox_allow = list(box_cfg.extra_allow)
    imap, smtp = FakeIMAP(messages), FakeSMTP()
    box = GmailMailbox(box_cfg, store, imap_factory=lambda h: imap, smtp_factory=lambda h: smtp, log=lambda t: None)
    return pipeline, store, box, imap, smtp


def poll(pipeline, box):
    runs = [pipeline.process(e, signature_note="gmail") for e in box.fetch_new()]
    return runs, box.deliver_pending()


class MailboxTests(unittest.TestCase):
    def test_authenticated_yale_sender_gets_an_answer_in_dry_run(self):
        pipeline, store, box, imap, smtp = connect([raw_mail()])
        runs, delivered = poll(pipeline, box)
        self.assertEqual(runs[0]["outcome"], "AUTO_SENT")
        self.assertIn("0.1 mm", runs[0]["draft"]["body"])
        self.assertEqual([d["status"] for d in delivered], ["dry_run"])
        self.assertEqual(smtp.sent, [])  # dry-run: nothing leaves the computer
        self.assertEqual(imap.seen, {b"1"})

    def test_sending_on_replies_in_thread_and_ignores_reply_to(self):
        mail = raw_mail(extra={"Reply-To": "attacker@evil.example"})
        pipeline, store, box, imap, smtp = connect([mail], send_mode="on")
        poll(pipeline, box)
        self.assertEqual(len(smtp.sent), 1)
        reply, to_addrs = smtp.sent[0]
        self.assertEqual(to_addrs, [TA])
        self.assertEqual(reply["To"], TA)
        self.assertEqual(reply["In-Reply-To"], "<q1@mail.yale.edu>")
        self.assertIn("<q1@mail.yale.edu>", reply["References"])
        self.assertIn("John, Northfield Outdoor Labs", reply["From"])
        self.assertEqual(reply["Auto-Submitted"], "auto-replied")

    def test_conversation_continues_in_the_same_thread(self):
        pipeline, store, box, imap, smtp = connect([raw_mail()], send_mode="on")
        first, _ = poll(pipeline, box)
        our_id = smtp.sent[0][0]["Message-ID"]
        # The TA's client only sets In-Reply-To (no References): still the same conversation.
        imap.add(raw_mail(msgid="<q2@mail.yale.edu>", in_reply_to=our_id,
                                       subject="Re: TB-1 question", body="Thanks. And what O-ring cross-section?"))
        second, _ = poll(pipeline, box)
        self.assertEqual(second[0]["email"]["thread_id"], first[0]["email"]["thread_id"])
        memory = next(s for s in second[0]["trace"] if s["key"] == "memory")
        self.assertIn("Loaded 2", memory["detail"])  # the TA's first email and our reply

    def test_forged_allowlisted_sender_is_held_without_tokens(self):
        forged = raw_mail(sender="Kevin Zhang <kevin.zhang@hongyuan-mold.example>",
                          auth="dkim=none; spf=fail; dmarc=fail header.from=hongyuan-mold.example")
        pipeline, store, box, imap, smtp = connect([forged], send_mode="on")
        runs, delivered = poll(pipeline, box)
        self.assertEqual(runs[0]["outcome"], "HELD")
        self.assertIn("DKIM/DMARC", runs[0]["sender"]["reason"])
        self.assertEqual(runs[0]["usage"]["calls"], 0)
        self.assertEqual(smtp.sent, [])

    def test_only_gmails_own_authentication_stamp_counts(self):
        msg = message_from_bytes(raw_mail(auth=None, extra={
            "Authentication-Results": "attacker.example; dkim=pass header.i=@yale.edu; dmarc=pass"}),
            policy=email_policy.default)
        event = to_event(msg.as_bytes(), GMAIL, lambda mid: None)
        self.assertFalse(event["message"]["auth"]["verified"])

    def test_unknown_sender_and_mailing_lists_get_no_reply(self):
        pipeline, store, box, imap, smtp = connect([
            raw_mail(sender="Someone <someone@gmail.com>", msgid="<a@gmail.com>",
                     auth="dkim=pass header.i=@gmail.com; dmarc=pass header.from=gmail.com"),
            raw_mail(msgid="<news@mail.yale.edu>", extra={"Precedence": "bulk"}),
        ], send_mode="on")
        runs, _ = poll(pipeline, box)
        self.assertEqual([r["outcome"] for r in runs], ["HELD", "FYI"])
        self.assertEqual(smtp.sent, [])

    def test_per_sender_daily_cap(self):
        mails = [raw_mail(msgid=f"<cap{i}@mail.yale.edu>", subject=f"Question {i}") for i in range(3)]
        pipeline, store, box, imap, smtp = connect(mails, send_mode="on", per_sender_daily_cap=2)
        _, delivered = poll(pipeline, box)
        self.assertEqual([d["status"] for d in delivered], ["sent", "sent", "capped_sender"])
        self.assertEqual(len(smtp.sent), 2)

    def test_human_approval_is_delivered_too(self):
        mail = raw_mail(body="Can you confirm a price of USD 3.85 for 20k pcs?")
        pipeline, store, box, imap, smtp = connect([mail], send_mode="on")
        store.set_settings({"risk_tolerance": "low"})  # holding reply waits for Wei
        runs, delivered = poll(pipeline, box)
        self.assertEqual(runs[0]["outcome"], "ESCALATED")
        self.assertEqual(delivered, [])
        self.assertTrue(pipeline.approve(runs[0]["id"])["ok"])
        self.assertEqual([d["status"] for d in box.deliver_pending()], ["sent"])

    def test_demo_events_are_never_delivered(self):
        from tests.test_pipeline import ROUTINE
        pipeline, store, box, imap, smtp = connect([], send_mode="on")
        self.assertEqual(pipeline.process(copy.deepcopy(ROUTINE))["outcome"], "AUTO_SENT")
        self.assertEqual(box.deliver_pending(), [])
        self.assertEqual(smtp.sent, [])

    def test_old_unread_mail_is_left_alone(self):
        old = datetime.now(timezone.utc) - timedelta(days=30)
        pipeline, store, box, imap, smtp = connect([], send_mode="on")
        stale = imap.add(raw_mail(msgid="<old@mail.yale.edu>"), arrived=old)
        fresh = imap.add(raw_mail(msgid="<new@mail.yale.edu>"))
        runs, _ = poll(pipeline, box)
        self.assertEqual([r["email"]["message_id"] for r in runs], ["<new@mail.yale.edu>"])
        self.assertNotIn(stale, imap.seen)  # stays unread in the real inbox
        self.assertIn(fresh, imap.seen)
        self.assertEqual(len(smtp.sent), 1)

    def test_build_reply_keeps_reference_chain(self):
        cfg = MailboxConfig(address=GMAIL, app_password="x")
        reply = build_reply(cfg, to_addr=TA, subject="Re: hi", body="Hello",
                            original={"message_id": "<b@x>", "headers": {"References": "<a@x>"}})
        self.assertEqual(reply["References"], "<a@x> <b@x>")


if __name__ == "__main__":
    unittest.main()
