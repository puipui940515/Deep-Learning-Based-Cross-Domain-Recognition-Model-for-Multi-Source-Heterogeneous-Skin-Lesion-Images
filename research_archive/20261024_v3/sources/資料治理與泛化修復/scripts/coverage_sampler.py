from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterator

import numpy as np
from torch.utils.data import Sampler


class FullCoverageCappedSampler(Sampler[int]):
    """每個 epoch 完整覆蓋所有列，再有限補抽較小來源與少數類別。

    每一輪補抽在同一來源內採無放回抽樣，因此任何樣本每個 epoch
    最多出現 ``max_repeats`` 次。補抽機率使用來源內類別數量的
    ``count ** (-class_balance_alpha)``，不會捨棄常見類別的基礎覆蓋。
    """

    def __init__(
        self,
        rows: list[dict],
        *,
        class_balance_alpha: float = 0.5,
        max_repeats: int = 2,
        seed: int = 17,
    ) -> None:
        if max_repeats < 1:
            raise ValueError("max_repeats 必須至少為 1")
        if not 0 <= class_balance_alpha <= 1:
            raise ValueError("class_balance_alpha 必須介於 0 與 1")
        self.rows = rows
        self.class_balance_alpha = class_balance_alpha
        self.max_repeats = max_repeats
        self.seed = seed
        self.epoch = 0

        source_indices: dict[str, list[int]] = defaultdict(list)
        self.class_counts = Counter()
        for index, row in enumerate(rows):
            source = row["source"]
            label = int(row["label"])
            source_indices[source].append(index)
            self.class_counts[(source, label)] += 1
        if not source_indices:
            raise ValueError("rows 不可為空")
        self.source_indices = {source: np.asarray(indices, dtype=np.int64) for source, indices in source_indices.items()}
        self.largest_source_size = max(len(indices) for indices in self.source_indices.values())
        self.source_epoch_counts = {
            source: size + min(self.largest_source_size - size, size * (max_repeats - 1))
            for source, indices in self.source_indices.items()
            for size in [len(indices)]
        }
        self.num_samples = sum(self.source_epoch_counts.values())

    def __len__(self) -> int:
        return self.num_samples

    def set_epoch(self, epoch: int) -> None:
        self.epoch = int(epoch)

    def _weighted_without_replacement(
        self,
        rng: np.random.Generator,
        source: str,
        indices: np.ndarray,
        count: int,
    ) -> list[int]:
        if count <= 0:
            return []
        labels = np.asarray([int(self.rows[int(index)]["label"]) for index in indices], dtype=np.int64)
        weights = np.asarray(
            [self.class_counts[(source, int(label))] ** (-self.class_balance_alpha) for label in labels],
            dtype=np.float64,
        )
        weights /= weights.sum()
        selected = rng.choice(indices, size=count, replace=False, p=weights)
        return [int(index) for index in selected]

    def __iter__(self) -> Iterator[int]:
        rng = np.random.default_rng(self.seed + self.epoch)
        epoch_indices: list[int] = []
        for source in sorted(self.source_indices):
            indices = self.source_indices[source].copy()
            rng.shuffle(indices)
            epoch_indices.extend(int(index) for index in indices)
            remaining = self.source_epoch_counts[source] - len(indices)
            for _repeat_round in range(self.max_repeats - 1):
                if remaining <= 0:
                    break
                take = min(remaining, len(indices))
                epoch_indices.extend(self._weighted_without_replacement(rng, source, indices, take))
                remaining -= take
        rng.shuffle(epoch_indices)
        self.epoch += 1
        return iter(epoch_indices)

    def audit(self) -> dict:
        unique_source_counts = {source: len(indices) for source, indices in self.source_indices.items()}
        return {
            "method": "full_coverage_capped_oversampling",
            "unique_samples": len(self.rows),
            "samples_per_epoch": self.num_samples,
            "coverage_guarantee": "每個 epoch 每筆訓練資料至少一次",
            "max_repeats_per_sample_per_epoch": self.max_repeats,
            "class_balance_alpha_for_extras": self.class_balance_alpha,
            "unique_source_counts": unique_source_counts,
            "source_samples_per_epoch": self.source_epoch_counts,
            "source_share_per_epoch": {
                source: count / self.num_samples for source, count in self.source_epoch_counts.items()
            },
        }

