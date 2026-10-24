"""Bind safety: the dashboard has no login, so it only ever listens on loopback or Fly.io's private network."""

import socket
import unittest
from types import SimpleNamespace

from supplier_agent.config import AppConfig
from supplier_agent.server import Handler, resolve_fly_private, run_server


def resolver_for(*addresses):
    def resolve(host, port, family=0):
        if not addresses:
            raise socket.gaierror("no such host")
        return [(socket.AF_INET6, socket.SOCK_STREAM, 0, "", (a, 0, 0, 0)) for a in addresses]
    return resolve


def handler_with(host_header: str, *, host: str, fly_private: bool) -> Handler:
    handler = Handler.__new__(Handler)  # no socket needed to test the Host check
    handler.server = SimpleNamespace(app=SimpleNamespace(config=SimpleNamespace(host=host, fly_private=fly_private)))
    handler.headers = {"Host": host_header}
    return handler


class FlyPrivateBindTests(unittest.TestCase):
    def test_private_6pn_address_is_used(self):
        self.assertEqual(resolve_fly_private(resolver_for("fdaa:0:1:a7b:1::2")), "fdaa:0:1:a7b:1::2")

    def test_public_or_missing_address_is_refused(self):
        for resolver in (resolver_for("2a09:8280:1::1"), resolver_for("::"), resolver_for()):
            with self.assertRaises(SystemExit):
                resolve_fly_private(resolver)

    def test_run_server_refuses_a_public_address_even_in_private_mode(self):
        config = AppConfig.from_env()
        config.host, config.fly_private = "2a09:8280:1::1", True
        with self.assertRaises(SystemExit) as ctx:
            run_server(config, open_browser=False)
        self.assertIn("fdaa::/16", str(ctx.exception))

    def test_public_host_still_refused_without_auth(self):
        config = AppConfig.from_env()
        config.host = "0.0.0.0"
        with self.assertRaises(SystemExit):
            run_server(config, open_browser=False)

    def test_private_mode_only_accepts_localhost_host_header(self):
        """`fly proxy 8000` makes the browser send Host: localhost:8000; anything else is DNS rebinding."""
        self.assertTrue(handler_with("127.0.0.1:8000", host="fdaa::2", fly_private=True)._host_ok())
        self.assertTrue(handler_with("localhost:8000", host="fdaa::2", fly_private=True)._host_ok())
        self.assertFalse(handler_with("evil.example:8000", host="fdaa::2", fly_private=True)._host_ok())


if __name__ == "__main__":
    unittest.main()
