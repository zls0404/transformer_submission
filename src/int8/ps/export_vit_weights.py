"""导出 ViT 权重、输入和参考 logits。输出到 assets 目录；模型来源和依赖按脚本配置。"""
import os

import numpy as np
import torch
import timm
from PIL import Image
from timm.data import resolve_data_config, create_transform

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

MODEL_NAME = "vit_tiny_patch16_224"

model = timm.create_model(MODEL_NAME, pretrained=True)
model.eval()

cfg = resolve_data_config({}, model=model)
transform = create_transform(**cfg)
print("Preprocessing config:", cfg)

img = Image.open(os.path.join(ASSETS, "sample_dog.jpg")).convert("RGB")
input_tensor = transform(img).unsqueeze(0)  # (1,3,224,224)

with torch.no_grad():
    logits = model(input_tensor)

probs = torch.softmax(logits, dim=1)[0]
top5 = torch.topk(probs, 5)
print("\nPyTorch reference top-5:")
with open(os.path.join(ASSETS, "imagenet_classes.txt")) as f:
    classes = [line.strip() for line in f]
for score, idx in zip(top5.values, top5.indices):
    print(f"  {classes[idx]:30s} {score.item()*100:.2f}%")

state_dict = {k: v.detach().numpy() for k, v in model.state_dict().items()}
np.savez(os.path.join(ASSETS, "vit_tiny_weights.npz"), **state_dict)
np.save(os.path.join(ASSETS, "vit_input.npy"), input_tensor.numpy())
np.save(os.path.join(ASSETS, "vit_reference_logits.npy"), logits.numpy())

print(f"\nExported {len(state_dict)} weight tensors to assets/vit_tiny_weights.npz")
print("Saved assets/vit_input.npy and assets/vit_reference_logits.npy")

total_params = sum(v.size for v in state_dict.values())
print(f"Total parameters: {total_params:,}")
