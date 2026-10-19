# 판교세븐 구내식당 식단

공식 게시판의 PDF를 읽어 모바일·PC용 식단 페이지로 표시합니다. Python은 GitHub Actions에서 실행되며 이용자 설치는 필요 없습니다. 공식 서비스가 아닌 편의용 페이지입니다.

## 최초 배포 (한 번만)

1. GitHub에 로그인하고 빈 **Public** 저장소(예: `pvv-menu`)를 만듭니다. 무료 계정에서 Pages를 쓰려면 공개 저장소를 사용합니다.
2. **이 README가 있는 폴더의 내용**을 저장소 `main` 브랜치 최상위에 올립니다. `.github/workflows/pages.yml`도 반드시 포함하세요. `github-pages` 폴더째 상위에 넣으면 실행되지 않습니다.
3. 저장소 **Settings → Pages → Build and deployment → Source**에서 **GitHub Actions**를 선택합니다.
4. **Actions → Update menu and deploy Pages → Run workflow → main → Run workflow**로 첫 배포를 실행합니다. 파일 업로드 직후 Pages 설정 전 실행된 작업이 실패했다면 다시 실행하면 됩니다.
5. 성공한 실행의 `deploy` 또는 **Settings → Pages → Visit site**에서 주소를 확인하고 공유합니다. 보통 `https://계정명.github.io/pvv-menu/`입니다.

API 키, 별도 서버, PC 예약 작업은 필요 없습니다. 저장소를 만든 사용자가 Actions 사용 권한을 가지고 있어야 합니다.

### Git으로 올리는 방법

이 폴더에서 아래 명령을 실행합니다. `YOUR_ACCOUNT`와 저장소 이름을 실제 값으로 바꾸세요. GitHub 인증이 필요합니다.

```sh
git init -b main
git add .
git commit -m "Add cafeteria menu Pages deployment"
git remote add origin https://github.com/YOUR_ACCOUNT/pvv-menu.git
git push -u origin main
```

## 자동 갱신

- 평일 한국 시간 07:17~19:17 매시간 확인합니다. 예약 실행은 GitHub 사정으로 지연되거나 누락될 수 있습니다.
- 코드 변경(main push), Actions의 Run workflow로도 즉시 갱신합니다.
- 최근 4주를 표시합니다. 매 실행 PDF를 다시 받아 같은 게시글의 수정도 반영합니다.
- 마지막 확인 시각은 한국 시간입니다. 열어둔 탭은 새로고침해야 새 배포를 읽습니다.
- 수집·검증 실패 시 배포하지 않으므로 기존 공개 페이지가 유지됩니다. Actions의 빨간 실행과 Build latest menu 로그를 확인하세요.
- 공개 저장소는 활동이 60일 없으면 예약 실행이 비활성화될 수 있습니다. Actions에서 다시 활성화하세요.
- 이 구성은 식단 변경이 없어도 확인 시각 갱신을 위해 다시 배포합니다.

## 로컬 확인

Python 3.13 기준:

```sh
python -m pip install -r requirements.txt
python pvv_menu.py --weeks 4
python verify_site.py
python -m http.server 8000 --directory site
```

브라우저에서 http://localhost:8000 을 엽니다.

## 공개 범위와 유지보수

공개 저장소에는 수집 코드·화면·배포 설정만 올립니다. `.gitignore`가 PDF 캐시, 생성된 페이지, 로그를 제외합니다. Pages에는 생성된 `site/`만 배포합니다. 원본 PDF는 복제해서 게시하지 않고 공식 사이트로 연결합니다.

메뉴와 운영 시간은 공식 게시판을 우선 확인하세요. PDF 표 양식이 크게 바뀌면 파서를 수정해야 할 수 있습니다. 사이트 출처는 http://www.pvv.co.kr/bbs/index.php?page=1&code=bbs_menu01 입니다.

기존 PC용 `식단보기.bat`와 Windows 예약 작업은 이 배포 폴더와 별개로 계속 동작합니다.
