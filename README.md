# AtlasOptimizer
<img width="1656" height="868" alt="image" src="https://github.com/user-attachments/assets/ede2c0b6-25ba-4897-b14e-7d793834b96b" />

FX 시퀀스 아틀라스(Flipbook Texture)의 여백을 자동으로 제거하고 최적화하는 툴.

## Features

- **Auto Fit** - 전체 프레임 합집합 바운딩 박스 자동 산출, 여백 제거
- **Free Transform** - Photoshop 스타일 기즈모 (스케일/회전/이동)
- **Stagger Pack** - 인접 4프레임을 RGBA 채널에 분산 배치, 텍스처 압축 최적화
- **Sequence Input** - 아틀라스 1장 또는 시퀀스 이미지 여러 장 입력 지원
- **RGBA Channel Viewer** - 채널별 개별 확인
- **Ghost Mode** - 전후 프레임 Screen 블렌딩 프리뷰

## Requirements

- **OS**: Windows 10/11
- **Python**: 3.10 이상
- **Dependencies**: Pillow, NumPy, PyQt5

## Install & Run

`run.bat` 실행

## Usage

1. **Load** - 아틀라스 이미지 1장 또는 시퀀스 이미지 여러 장 선택
2. **Auto Fit** - 자동으로 바운딩 박스 계산 및 크롭
3. **Optimize** - 최적화된 아틀라스 생성
4. **Stagger** - RGBA 채널 패킹 (선택)
5. **Save** - PNG, TGA, JPG, GIF 저장

## License

MIT
