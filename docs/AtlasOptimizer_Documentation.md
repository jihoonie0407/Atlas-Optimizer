# AtlasOptimizer - FX 시퀀스 아틀라스 최적화 툴

---

## 1. 개요

### 배경

외부에서 가져온 FX 시퀀스 아틀라스(Flipbook Texture)는 프레임별 여백이 크게 잡혀 있어 텍스처 공간 낭비가 심했다. 모바일/콘솔 등 텍스처 사이즈 제약이 큰 환경에서는 이 여백이 곧 메모리 낭비이자 오버드로우 증가로 이어진다.

기존에는 아티스트가 Photoshop에서 수작업으로 크롭하거나, 여백을 감수하고 그대로 사용하고 있었다. 16~64프레임 아틀라스를 일일이 편집하는 건 비현실적이었기 때문이다.

### 목표

1. **아틀라스 점유율 개선** - 전체 프레임의 합집합 바운딩 박스를 자동 산출하여 여백을 제거하고, 유효 영역만으로 아틀라스를 재구성
2. **오버드로우 감소** - 실제 사용 영역이 줄어들면서 런타임 렌더링 비용도 절감
3. **Stagger Pack** - 인접 프레임을 RGBA 채널에 분산 배치하여 텍스처 압축 아티팩트 최소화
4. **아티스트 친화적** - 더블클릭으로 실행, 실시간 프리뷰, Photoshop과 유사한 조작 방식

### 접근 방식

Houdini COPs의 **Demosaic/Mosaic** 개념을 차용했다. 아틀라스를 개별 프레임으로 분리(Demosaic)하고, 프레임 단위로 변형(Transform)한 뒤, 다시 아틀라스로 재구성(Mosaic)하는 파이프라인이다.

```
Atlas Input → Demosaic → Transform (Auto BBox / Manual) → Mosaic → Final Scale → Atlas Output
                                                        → Stagger Pack → Stagger Atlas Output
```

기술 스택은 **Python + PyQt5 + Pillow + NumPy**로 결정했다. Gradio도 검토했으나, Photoshop 스타일의 Free Transform 기즈모(드래그/회전/스케일 핸들)를 구현하려면 네이티브 위젯이 필요했다. 배포는 **PyInstaller**로 단일 exe 패키징.

---

## 2. 결과

### 주요 기능

| 기능 | 설명 |
|------|------|
| **자동 그리드 감지** | 이미지 로드 시 알파/밝기 분석으로 Row/Column 자동 판별 |
| **Auto Fit** | 전체 프레임 합집합 바운딩 박스 산출 → Scale/Translate 자동 설정 |
| **Free Transform** | Photoshop 스타일 기즈모 - 코너(균등 스케일), 엣지(축별 스케일), 외곽(회전), 중앙(이동), 휠(스케일) |
| **Location X/Y** | 원점 기준 이동량 슬라이더, AutoFit 시 bbox 오프셋 자동 반영 |
| **Ghost 모드** | 현재 프레임 전후 프레임을 Screen 블렌딩으로 반투명 표시 (1~32 Steps) |
| **RGBA 채널 뷰어** | Xform/Result 양쪽 패널에 R/G/B/A 개별 토글, 단일 채널은 흑백 표시 |
| **Gamma 보정** | 프리뷰 및 최종 출력에 pow 기반 감마 적용 |
| **해상도 프리셋** | 128 / 256 / 512 / 1024 / 2048 / 4096 선택 |
| **다중 포맷 저장** | PNG, TGA, JPG, GIF 지원 |
| **Grid 오버레이** | 결과 아틀라스에 프레임 경계선 표시 |
| **Stagger Pack** | 인접 4프레임을 1셀의 RGBA 채널에 분산 배치, 텍스처 압축 최적화 |
| **시퀀스 입력** | 1장=Atlas, 여러 장=Sequence 자동 인식, 시퀀스→아틀라스 자동 생성 |

### UI 구성

```
┌──────────────┬──────────────────┬──────────────┐
│ Input (Atlas)│ Xform (Free Xfm) │ Result(Atlas)│
│              │                  │              │
│  Row: Col:   │ Ghost Steps Reset│ Size: - + Grid│
│              │ AutoFit Pad RGBA │         RGBA │
│  ┌────────┐  │  ┌────────────┐  │  ┌────────┐  │
│  │        │  │  │            │  │  │        │  │
│  │ Input  │  │  │  Canvas    │  │  │ Result │  │
│  │Preview │  │  │  (Gizmo)   │  │  │Preview │  │
│  │        │  │  │            │  │  │        │  │
│  └────────┘  │  └────────────┘  │  └────────┘  │
│  [  Load  ]  │ Loc X/Y Sca X/Y │[Optimize][Stagger]│
│  file info   │ Rot Gam timeline │ [    Save    ]│
│              │                  │ v1.1.0       │
└──────────────┴──────────────────┴──────────────┘
```

- **3패널 균등 배치** - 고정 높이 상/하단 컨테이너로 프리뷰 영역 동일 크기 보장
- **다크 테마** - 골드 악센트(#e8a838), Segoe UI 폰트
- **최소 창 크기 1400x820** - 4K 모니터 대응

### Stagger Pack

#### 개념

인접한 4개 프레임의 그레이스케일 데이터를 하나의 셀의 R/G/B/A 채널에 분산 배치하는 방식이다. DXT/BC 등 블록 압축 시 인접 프레임은 시각적으로 유사하므로 채널 간 값 차이가 작아 아티팩트가 최소화된다.

```
4x4 아틀라스 (16프레임) → Stagger → 2x2 아틀라스 (4셀)

셀 0: R=프레임1, G=프레임2, B=프레임3, A=프레임4
셀 1: R=프레임5, G=프레임6, B=프레임7, A=프레임8
셀 2: R=프레임9, G=프레임10, B=프레임11, A=프레임12
셀 3: R=프레임13, G=프레임14, B=프레임15, A=프레임16
```

#### Super Pack과의 차이

| | Stagger Pack | Super Pack |
|---|---|---|
| **배치** | 인접 4프레임 → RGBA | 64프레임씩 채널 순차 |
| **셀(0,0)의 RGBA** | 프레임 1,2,3,4 | 프레임 1,65,129,193 |
| **채널 간 유사도** | 높음 (인접 프레임) | 낮음 (먼 프레임) |
| **압축 아티팩트** | **적음** | 많음 |
| **셰이더 복잡도** | 높음 (보간 시 2회 샘플링) | 낮음 |

#### 컬러 입력 처리

Stagger Pack은 1프레임 = 1채널이므로 컬러 데이터는 구조적으로 저장 불가. 자동으로 그레이스케일 변환 후 패킹한다.

| 입력 타입 | 변환 방식 |
|---|---|
| 그레이스케일 (Alpha만 있는 FX) | Alpha 채널 사용 |
| 컬러 RGB + Alpha | 전체 프레임 기준 Alpha vs Luminance 자동 판별 |
| 컬러 RGB (Alpha 없음) | Luminance 변환: `0.299*R + 0.587*G + 0.114*B` |

- Alpha/Luminance 판별은 **전체 프레임의 표준편차 합산** 비교로 1회만 결정하여 채널 간 일관성 보장

#### 리사이즈 순서 (핵심)

```
잘못된 순서: 프레임 패킹 → LANCZOS 리사이즈 → 보간 아티팩트 발생 ✗
올바른 순서: 프레임 LANCZOS 리사이즈 → 패킹 → 채널 데이터 보존 ✓
```

패킹된 이미지에 LANCZOS 리사이즈를 적용하면 채널 간 독립적인 프레임 데이터에 보간 ringing이 발생하여 결과가 깨진다. 따라서 각 프레임을 **패킹 전에 목표 셀 크기로 리사이즈**한 뒤 패킹한다.

### 시퀀스 입력

파일 다이얼로그에서 **1장 선택 = Atlas 모드**, **여러 장 선택 = Sequence 모드**로 자동 인식.

| 항목 | Atlas 모드 | Sequence 모드 |
|------|-----------|--------------|
| **입력** | 아틀라스 이미지 1장 | 시퀀스 이미지 N장 |
| **그리드** | 알파/밝기 분석 자동 감지 | √N 정사각 그리드 자동 계산 |
| **Demosaic** | 아틀라스 → 프레임 분리 | 불필요 (이미 개별 프레임) |
| **이후 파이프라인** | 동일 | 동일 |
| **크기 검증** | - | 모든 프레임 동일 크기 필수, 불일치 시 경고 |

### 성능 최적화

- **프레임 numpy 사전 변환** - Demosaic 시 1회만 float32(0-1) 변환 후 캐싱
- **Ghost 결과 캐싱** - 프레임/스텝 변경 시에만 재계산, 감마/채널 변경은 캐시 재사용
- **병렬 렌더링** - Mosaic/Stagger 시 ThreadPoolExecutor로 프레임별 병렬 처리
- **QPainter 실시간 렌더링** - Transform 프리뷰는 PIL 변환 없이 QPainter로 직접 그리기

### 배포

- **단일 exe** (PyInstaller --onefile, ~54MB)
- Python 설치 불필요, 더블클릭으로 실행
- 불필요한 Qt 모듈 30+개 제외하여 용량 최적화
- Windows IME(한글 입력) 호환성 확보

---

## 3. 과정

### Phase 1: Atlas Crop & Optimize (v1.0.0)

#### 설계 및 기획

프로젝트 시작 전 CLAUDE.md에 전체 설계 문서를 작성했다. Houdini COPs의 Demosaic/Mosaic 개념을 중심으로 파이프라인을 설계하고, UI 요구사항과 성능 목표를 정의했다.

핵심 설계 원칙:
- **공통 Max BBox** - 프레임별 개별 bbox가 아닌, 전체 프레임 합집합 bbox 1개를 모든 프레임에 동일 적용
- **프리뷰는 QPainter, 최종만 PIL** - Demosaic 1회만 실행하고 Transform은 파라미터만 저장, 실제 연산은 최종 렌더링 때만
- **Photoshop과 유사한 UX** - Free Transform 기즈모, JumpSlider, 실시간 프리뷰

#### Core 로직 구현

파일 구조를 `core/` 모듈로 분리하여 구현했다.

1. **demosaic.py** - 아틀라스를 Row × Column 그리드로 분할하여 개별 프레임 배열 반환
2. **bbox.py** - 알파 채널 기반 바운딩 박스 계산
3. **transform.py** - crop, scale 등 프레임 변환
4. **mosaic.py** - 편집된 프레임들을 원본 순서대로 아틀라스로 재구성

#### UI 구현 (PyQt5)

초기에는 Gradio를 검토했으나, Free Transform 기즈모(드래그 핸들로 스케일/회전/이동)를 구현하려면 Canvas 위에 직접 그리는 방식이 필요했다. PyQt5의 QPainter를 사용하면 실시간 프리뷰가 가능하고, PyInstaller로 exe 패키징도 간단했다.

주요 위젯:
- **ImagePreview** - QWidget 기반 이미지 프리뷰 (fit-to-widget, grid overlay)
- **TransformCanvas** - Free Transform 기즈모가 포함된 캔버스 (hit test, 커서 변경, 회전 커서)
- **JumpSlider** - 클릭 시 해당 위치로 즉시 이동하는 슬라이더

#### 기능 추가

- **자동 그리드 감지** - 후보 Row/Col 조합별로 셀 중심 vs 가장자리 콘텐츠 비율을 스코어링
- **RGBA 채널 뷰어** - 단일 채널은 흑백, 조합은 컬러+알파로 표시
- **Ghost 모드** - Screen 블렌딩으로 전후 프레임 누적 표시, 거리 기반 fade
- **Gamma 보정** - pow 함수 기반, 0과 1 보존

#### UI 스타일 리뉴얼

- **다크 테마 전면 개편** - 배경색 #1e1e1e, 골드 악센트 #e8a838, 그라디언트 primary 버튼
- **고정 높이 컨테이너** - TOP_H=82, BOT_H=158로 3패널 프리뷰 크기 통일
- **컨트롤 정렬** - Input의 Row/Col과 Xform의 Ghost Steps가 수평 정렬
- **Load 버튼 하단 이동** - Optimize와 같은 primary 스타일로 전체 폭 배치
- **버전 표시** - Result 패널 우측 하단에 `v1.1.0  jihoonie0407`

#### 성능 최적화

Ghost 모드에서 프레임 드랍이 발생하여 3가지 최적화를 적용했다:

1. **numpy 사전 변환** - Demosaic 시 모든 프레임을 float32(0-1)로 변환하여 캐싱
2. **Ghost 결과 캐싱** - (현재 프레임, 스텝 수, 활성화 여부)를 캐시 키로 사용
3. **0-1 정규화 공간 연산** - 루프 내 `/255`, `*255` 반복 제거, 최종 출력 때만 변환

#### 빌드 및 배포

- **PyInstaller --onefile** - 단일 exe로 배포, 공유폴더에 올려두면 팀 전체 사용
- **불필요 모듈 제외** - QtWebEngine, QtMultimedia, Qt3D, QtQml 등 30+개 모듈 제외
- **version_info.txt** - exe에 파일 정보 메타데이터 포함
- **아이콘 경로 수정** - `_resource_path()` 헬퍼로 개발 환경과 exe 환경 모두 동작
- **한글 IME 수정** - `QT_IM_MODULE=windows` 환경변수로 Windows IME 호환성 확보

### Phase 2: Stagger Pack & 시퀀스 입력 (v1.1.0)

#### Stagger Pack 구현

[flipbook-packer](https://github.com/stylerhall/flipbook-packer) 저장소를 분석하여 Stagger Pack 개념을 이해하고, 기존 파이프라인에 통합했다.

핵심 구현:
1. **core/stagger.py** - `_decide_channel()`, `_to_grayscale()`, `stagger_pack()` 3개 함수
2. **채널 판별** - 전체 프레임의 Alpha vs Luminance 표준편차 합산으로 1회 판단, 일관성 보장
3. **리사이즈 순서** - 프레임을 먼저 목표 셀 크기로 LANCZOS 리사이즈 후 패킹 (패킹 후 리사이즈 시 보간 아티팩트 발생하는 문제 해결)
4. **4의 배수가 아닌 경우** - 남는 채널은 0으로 채움

발견한 문제와 해결:
- **프레임별 채널 판별 불일치** - 프레임 A는 alpha, 프레임 B는 luminance로 섞이는 버그 → 전체 기준 1회 판별로 수정
- **LANCZOS 보간 깨짐** - 패킹 후 리사이즈 시 채널 간 ringing 아티팩트 → 리사이즈 순서 역전으로 해결

#### 시퀀스 입력 지원

기존 Load 버튼 하나로 Atlas/Sequence 모드를 자동 구분하도록 구현했다.

- **1장 선택** → Atlas 모드 (기존과 동일, 자동 그리드 감지)
- **여러 장 선택** → Sequence 모드 (√N 정사각 그리드, 빈 프레임 자동 패딩)
- **에러 핸들링** - 크기 불일치, 로드 실패 시 경고 다이얼로그 표시 (크래시 방지)

Sequence 모드에서는 Demosaic를 건너뛰고 프레임을 바로 파이프라인에 투입한다.

#### UI 추가

- **Stagger 버튼** - Optimize 옆에 가로 배치, 동일 primary 스타일
- **Result RGBA 뷰어** - Result 패널 상단에 R/G/B/A 토글 추가, Stagger 결과 채널별 확인
- **Location X/Y 슬라이더** - Scale X/Y 위에 배치, 캔버스 이동과 양방향 동기화, AutoFit 시 bbox 오프셋 자동 반영

---

## 기술 스택

| 항목 | 선택 | 이유 |
|------|------|------|
| 언어 | Python 3.13 | 이미지 처리 라이브러리 풍부 |
| 이미지 처리 | Pillow + NumPy | 경량, 충분한 기능 |
| UI | PyQt5 | Free Transform 기즈모 구현 가능, 실시간 QPainter |
| 배포 | PyInstaller (exe) | 아티스트가 더블클릭으로 실행 |

---

## 파일 구조

```
app.py              - 메인 앱 (~1700줄), VERSION = "1.1.0"
core/
  demosaic.py       - 아틀라스 → 프레임 분리
  mosaic.py         - 프레임 → 아틀라스 재구성
  bbox.py           - 바운딩 박스 계산
  transform.py      - crop, scale 변환
  stagger.py        - Stagger Pack 채널 패킹
utils/
  image_utils.py    - 이미지 로드/저장 유틸
build.bat           - PyInstaller 빌드 스크립트
version_info.txt    - exe 버전 메타데이터
icon.ico            - 앱 아이콘 (6사이즈)
docs/
  stagger_pack_spec.md - Stagger Pack 기획서
```

---

## 후속 과제

- **Super Pack** - RGB 192프레임 / RGBA 256프레임, 채널별 순차 배치
- **셰이더 템플릿** - Stagger Pack 결과를 언패킹하는 Unity/Unreal 셰이더 코드 제공
- **GitHub Releases 인앱 업데이트** - exe 자동 업데이트 시스템
- **Reference**: [Flipbook Texture Packing](https://realtimevfx.com/t/flipbook-texture-packing-atlas-super-pack-and-stagger-pack/5609)
