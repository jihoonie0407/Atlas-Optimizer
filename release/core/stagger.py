"""
Stagger Pack: 인접 4프레임을 1셀의 R/G/B/A 채널에 분산 배치
- 컬러 입력 → 그레이스케일(Luminance) 자동 변환
- 프레임 수가 4의 배수가 아니면 빈 채널은 0으로 채움
"""
import math
import numpy as np
from PIL import Image
from typing import List, Tuple


def _decide_channel(frames: list) -> str:
    """
    전체 프레임을 분석하여 alpha vs luminance 중 하나를 결정.
    모든 프레임에 동일하게 적용해야 채널 간 일관성이 유지됨.
    """
    total_a_std = 0.0
    total_l_std = 0.0

    for frame in frames:
        arr = np.array(frame)
        if frame.mode != 'RGBA':
            return 'luminance'

        r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]
        gray = (0.299 * r.astype(np.float32)
                + 0.587 * g.astype(np.float32)
                + 0.114 * b.astype(np.float32))

        total_a_std += np.std(a.astype(np.float32))
        total_l_std += np.std(gray)

    return 'alpha' if total_a_std >= total_l_std else 'luminance'


def _to_grayscale(frame: Image.Image, mode: str) -> np.ndarray:
    """
    프레임을 그레이스케일 numpy 배열로 변환 (uint8, H×W)
    mode='alpha' 또는 'luminance' — 전체 프레임에 동일 적용
    """
    arr = np.array(frame)

    if frame.mode == 'RGBA':
        if mode == 'alpha':
            return arr[:, :, 3]
        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
        gray = (0.299 * r.astype(np.float32)
                + 0.587 * g.astype(np.float32)
                + 0.114 * b.astype(np.float32))
        return np.clip(gray, 0, 255).astype(np.uint8)

    elif frame.mode == 'RGB':
        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
        gray = (0.299 * r.astype(np.float32)
                + 0.587 * g.astype(np.float32)
                + 0.114 * b.astype(np.float32))
        return np.clip(gray, 0, 255).astype(np.uint8)

    elif frame.mode in ('L', 'LA'):
        if frame.mode == 'LA':
            return arr[:, :, 0]
        return arr

    return np.array(frame.convert('L'))


def _next_pot(v):
    """v 이상의 최소 Power of Two 반환"""
    p = 1
    while p < v:
        p <<= 1
    return p


def optimal_stagger_grid(num_cells: int, fw: int, fh: int) -> Tuple[int, int]:
    """
    셀 수와 프레임 크기를 고려하여 POT 텍스처 면적이 최소인 그리드 반환.

    Args:
        num_cells: 패킹할 셀 수
        fw: 프레임 너비
        fh: 프레임 높이

    Returns:
        (rows, cols)
    """
    best_rows, best_cols = 1, num_cells
    best_pot_area = float('inf')
    best_max_dim = float('inf')
    best_waste = num_cells

    for r in range(1, num_cells + 1):
        c = math.ceil(num_cells / r)
        pot_w = _next_pot(fw * c)
        pot_h = _next_pot(fh * r)
        pot_area = pot_w * pot_h
        max_dim = max(pot_w, pot_h)
        waste = r * c - num_cells

        # 1순위: POT 면적 최소, 2순위: 최대 변 길이 최소 (정사각형 선호), 3순위: 빈 셀 최소
        if (pot_area < best_pot_area
            or (pot_area == best_pot_area and max_dim < best_max_dim)
            or (pot_area == best_pot_area and max_dim == best_max_dim and waste < best_waste)):
            best_pot_area = pot_area
            best_max_dim = max_dim
            best_rows, best_cols = r, c
            best_waste = waste

    return best_rows, best_cols


def stagger_pack(
    frames: List[Image.Image],
    rows: int,
    cols: int
) -> Tuple[Image.Image, int, int]:
    """
    프레임들을 Stagger Pack 방식으로 패킹

    Args:
        frames: Transform 적용된 프레임 리스트 (PIL Image)
        rows: 원본 행 수
        cols: 원본 열 수

    Returns:
        (packed_atlas, new_rows, new_cols)
    """
    if not frames:
        raise ValueError("프레임 리스트가 비어있습니다")

    total = len(frames)
    fw, fh = frames[0].size

    # 전체 프레임 기준으로 alpha/luminance 한 번만 결정
    channel_mode = _decide_channel(frames)

    # 그레이스케일 변환 (모든 프레임에 동일 모드 적용)
    grays = [_to_grayscale(f, channel_mode) for f in frames]

    # 4프레임씩 묶어서 셀 생성
    num_cells = math.ceil(total / 4)

    # 프레임 비율을 고려한 POT 최적 그리드 계산
    new_rows, new_cols = optimal_stagger_grid(num_cells, fw, fh)

    # 아틀라스 배열 생성 (H, W, 4채널 RGBA)
    atlas_h = fh * new_rows
    atlas_w = fw * new_cols
    atlas = np.zeros((atlas_h, atlas_w, 4), dtype=np.uint8)

    for cell_idx in range(num_cells):
        cell_row = cell_idx // new_cols
        cell_col = cell_idx % new_cols

        y0 = cell_row * fh
        x0 = cell_col * fw

        for ch in range(4):
            frame_idx = cell_idx * 4 + ch
            if frame_idx < total:
                atlas[y0:y0 + fh, x0:x0 + fw, ch] = grays[frame_idx]

    packed = Image.fromarray(atlas, 'RGBA')
    return packed, new_rows, new_cols
