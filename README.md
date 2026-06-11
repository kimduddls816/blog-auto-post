# 블로그 자동 발행 시스템

매일 오전 9시 자동으로 5개 글을 WordPress에 발행합니다.

## 세팅 방법

### 1. GitHub 레포 생성
- github.com → New repository → 이름: `blog-auto-post` → Create

### 2. 파일 업로드
이 폴더 전체를 레포에 업로드

### 3. GitHub Secrets 등록
레포 → Settings → Secrets and variables → Actions → New repository secret

| Name | Value |
|------|-------|
| `ANTHROPIC_API_KEY` | Anthropic API 키 |
| `WP_CLIENT_ID` | WordPress 앱 Client ID |
| `WP_CLIENT_SECRET` | WordPress 앱 Client Secret |
| `WP_USERNAME` | WordPress 로그인 이메일 |
| `WP_PASSWORD` | WordPress 로그인 비밀번호 |

### 4. 완료
매일 오전 9시 자동 실행됩니다.
Actions 탭에서 수동 실행도 가능합니다.
