import openai

response = openai.Image.create(
  prompt="a white siamese cat",
  n=1,
  size="1024x1024"
)
