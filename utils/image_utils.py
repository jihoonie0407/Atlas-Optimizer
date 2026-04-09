"""
이미지 로드/저장 유틸리티
"""
from PIL import Image
from pathlib import Path
from typing import Union, Optional


def load_image(path: Union[str, Path]) -> Image.Image:
    """
    이미지 로드 (RGBA 모드로 변환)

    Args:
        path: 이미지 파일 경로

    Returns:
        PIL Image (RGBA)
    """
    image = Image.open(path)
    if image.mode != 'RGBA':
        image = image.convert('RGBA')
    return image


def save_image(
    image: Image.Image,
    path: Union[str, Path],
    optimize: bool = False
) -> None:
    """
    이미지 저장

    Args:
        image: PIL Image
        path: 저장 경로
        optimize: PNG 최적화 여부
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # 확장자에 따라 저장
    suffix = path.suffix.lower()
    if suffix == '.png':
        image.save(path, 'PNG', optimize=optimize)
    elif suffix in ['.jpg', '.jpeg']:
        # JPEG는 알파 채널 미지원
        if image.mode == 'RGBA':
            image = image.convert('RGB')
        image.save(path, 'JPEG', quality=95)
    else:
        image.save(path)


def get_image_info(image: Image.Image) -> dict:
    """
    이미지 정보 반환

    Args:
        image: PIL Image

    Returns:
        이미지 정보 딕셔너리
    """
    return {
        'size': image.size,
        'mode': image.mode,
        'width': image.width,
        'height': image.height,
    }
