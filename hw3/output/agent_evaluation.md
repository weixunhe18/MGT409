# Agent Evaluation

## Identify ability — four test images

Run: `python agent.py --image data/test_images/*.jpeg`
Results: `output/identify_product.json`

| Image | Ground truth | Agent verdict | Match | Confidence |
|---|---|---|---|---|
| `image_01_true.jpeg` | true | true | `yale-dad-t-shirt` | high |
| `image_02_false.jpeg` | false | false | — | high |
| `image_03_true.jpeg` | true | true | `dry-zone-long-sleeve` | high |
| `image_04_false.jpeg` | false | false | — | high |

### My evaluation

my model performed 4/4, 100%. it was able to accurately describe the garment, match it to
catalogue.json. what we could improve is giving it tougher images where logos are stretched
or blurry.



##ad runs
- the ad failed both profile. video did not have any call to action, no price. it was unclear what the ad was trying to convince audience to do. 