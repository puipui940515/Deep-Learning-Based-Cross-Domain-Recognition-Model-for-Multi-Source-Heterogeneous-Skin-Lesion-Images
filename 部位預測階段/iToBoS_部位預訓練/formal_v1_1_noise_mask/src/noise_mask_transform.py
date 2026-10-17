from __future__ import annotations

import random

import torch
from torchvision import transforms


class RandomGaussianNoise:
    def __init__(self, probability: float, mean: float, standard_deviation: float):
        self.probability = float(probability)
        self.mean = float(mean)
        self.standard_deviation = float(standard_deviation)

    def __call__(self, tensor: torch.Tensor) -> torch.Tensor:
        if random.random() >= self.probability:
            return tensor
        noise = torch.randn_like(tensor) * self.standard_deviation + self.mean
        return torch.clamp(tensor + noise, 0.0, 1.0)


def build_transform(config: dict, training: bool):
    size = int(config["image_size"])
    if training:
        noise = config["gaussian_noise"]
        erasing = config["random_erasing"]
        operations = [
            transforms.RandomRotation(float(config["rotation_degrees"])),
            transforms.RandomResizedCrop(
                size,
                scale=tuple(config["random_resized_crop_scale"]),
                ratio=(0.9, 1.1),
            ),
            transforms.ColorJitter(
                brightness=config["color_jitter"],
                contrast=config["color_jitter"],
                saturation=config["color_jitter"],
            ),
            transforms.ToTensor(),
            RandomGaussianNoise(
                probability=noise["probability"],
                mean=noise["mean"],
                standard_deviation=noise["standard_deviation"],
            ),
            transforms.RandomErasing(
                p=erasing["probability"],
                scale=tuple(erasing["area_scale"]),
                ratio=tuple(erasing["aspect_ratio"]),
                value="random",
            ),
        ]
    else:
        operations = [
            transforms.Resize((size, size)),
            transforms.ToTensor(),
        ]
    operations.append(
        transforms.Normalize(
            [0.485, 0.456, 0.406],
            [0.229, 0.224, 0.225],
        )
    )
    return transforms.Compose(operations)

