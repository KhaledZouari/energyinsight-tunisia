"""Render the held-out confusion matrix from published aggregate metrics only."""
from pathlib import Path
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def main():
    root = Path(__file__).resolve().parents[1]
    metrics = json.loads((root / 'docs/results/test_metrics.json').read_text(encoding='utf-8'))
    if metrics['evaluation_set'] != 'test':
        raise ValueError('Only held-out test metrics may be rendered')
    matrix = np.array([[metrics['tn'], metrics['fp']], [metrics['fn'], metrics['tp']]])
    fig, ax = plt.subplots(figsize=(8, 6.7))
    fig.patch.set_facecolor('white')
    ax.imshow(matrix, cmap='Blues')
    descriptions = [['True negatives', 'False positives'], ['False negatives', 'True positives']]
    for i in range(2):
        for j in range(2):
            ax.text(j, i, f'{matrix[i, j]:,}\n{descriptions[i][j]}', ha='center', va='center',
                    fontsize=15, color='white' if i == 0 and j == 0 else '#16324f')
    ax.set_xticks([0, 1], ['Negative label', 'Positive label'])
    ax.set_yticks([0, 1], ['Negative label', 'Positive label'])
    ax.set_xlabel('Predicted class', fontsize=12, labelpad=12)
    ax.set_ylabel('Actual historical label', fontsize=12, labelpad=12)
    ax.set_title(f'Independent test evaluation\nHistGradientBoosting | {matrix.sum():,} customers',
                 fontsize=16, pad=20)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.text(.5, .025,
             f'Precision {metrics["precision"]:.2%}  |  Recall {metrics["recall"]:.2%}  |  '
             f'Threshold {metrics["threshold"]:.4f}', ha='center', fontsize=11, color='#334155')
    fig.tight_layout(rect=(0, .045, 1, 1))
    target = root / 'docs/images/test-confusion-matrix.png'
    target.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(target, dpi=180, facecolor='white')
    plt.close(fig)
    print(target.relative_to(root).as_posix())


if __name__ == '__main__':
    main()
