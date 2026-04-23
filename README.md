# AtlasOptimizer v1.2.2
<img width="1652" height="900" alt="image" src="https://github.com/user-attachments/assets/3a69bca1-d6b6-4c9e-8c98-6c4c88ca9532" />


FX 시퀀스 아틀라스(Flipbook Texture)의 여백을 자동으로 제거하고 최적화하는 툴.

## Features

- **Auto Fit** - 전체 프레임 합집합 바운딩 박스 자동 산출, 여백 제거
- **Free Transform** - Photoshop 스타일 기즈모 (스케일/회전/이동)
- **Stagger Pack** - 인접 4프레임을 RGBA 채널에 분산 배치, 텍스처 압축 최적화
- **Sequence Input** - 아틀라스 1장 또는 시퀀스 이미지 여러 장 입력 지원
- **RGBA Channel Viewer** - 채널별 개별 확인
- **Ghost Mode** - 전후 프레임 Screen 블렌딩 프리뷰
- **Drag & Drop** - 이미지 파일을 창에 드래그앤드롭하여 바로 로드
- **Check Update** - 인앱 업데이트 버튼 (GitHub에서 최신 버전 자동 다운로드)

## Requirements

- **OS**: Windows 10/11
- **Python**: 3.10 이상
- **Dependencies**: Pillow, NumPy, PyQt5

## Install & Run

`run.bat` 실행

## Usage

1. **Load** - 아틀라스 이미지 1장 또는 시퀀스 이미지 여러 장 선택 (드래그앤드롭 또는 Load 버튼)
2. **Auto Fit** - 자동으로 바운딩 박스 계산 및 크롭
3. **Optimize** - 최적화된 아틀라스 생성
4. **Stagger** - RGBA 채널 패킹 (선택)
5. **Save** - PNG, TGA, JPG, GIF 저장

## Changelog

### v1.2.2
- **출력 해상도 POT 보장** - Optimize/Stagger 출력이 항상 Power of Two 해상도로 생성 (1024x1023 같은 엔진 압축 불가 케이스 수정)
- **Stagger 채널 데이터 보존** - 패킹된 RGBA 채널에 LANCZOS 리사이즈 대신 zero padding 적용, 채널 분리값 오염 방지
- **Stagger grayscale 변환 개선** - alpha 채널 자동 감지 제거, 항상 RGB luminance 기준으로 변환 (stagger에서 A채널은 프레임 저장용)

### v1.2.1
- **Stagger Pack 그리드 최적화** - 프레임 비율과 POT(Power of Two) 텍스처 면적을 고려하여 최적 그리드 자동 계산. 정사각형 강제 대신 실제 텍스처 메모리를 최소화하는 배치 선택 (예: 8프레임 → 기존 2x2에서 1x2로, 빈 셀 제거)

## License

MIT
