# rye の仮想環境および Docker 利用ガイド

## 概要

rye は Python のプロジェクト管理およびパッケージ管理ツールです。コードのフォーマット、リント、テスト、ビルド、公開など、Python開発における多くの側面を統一的なインターフェースで扱うことを目指しています。
仮想環境や Docker コンテナで `rye` を利用することで、開発環境と本番環境の一貫性を保ち、依存関係の衝突を避け、再現性の高いビルドプロセスを構築できます。
このドキュメントでは、一般的なLinuxベースの仮想環境（CI/CD環境などを含む）および Docker コンテナで `rye` をセットアップし利用するための基本的な方法と注意点を説明します。

## 一般的なLinux仮想環境での利用

Jules のような CI/CD 環境や、その他の一時的なLinux仮想環境で `rye` を利用する場合、以下の点に注意してセットアップを行います。

### インストール
`rye` のインストールは、公式のインストーラーを使用するのが最も簡単です。非対話的な環境では、プロンプトをスキップするオプションを利用します。

```bash
# 最新版を非対話的にインストール
curl -sSf https://rye.astral.sh/get | bash -s -- --yes
```

特定のバージョンの `rye` をインストールしたい場合や、`rye` が内部で使用する Python のバージョンを指定したい場合は、環境変数を利用できます。

```bash
# 特定バージョンの rye をインストール (例: 0.30.0)
curl -sSf https://rye.astral.sh/get | RYE_VERSION="0.30.0" RYE_INSTALL_OPTION="--yes" bash

# プロジェクトで使用する Python と同じバージョンを内部ツールチェインとして指定
# これにより Python のダウンロードが1回で済む可能性があります
curl -sSf https://rye.astral.sh/get | RYE_TOOLCHAIN_VERSION="3.11" RYE_INSTALL_OPTION="--yes" bash
```

インストール後、`rye` の実行ファイルや `shims` ディレクトリにパスを通す必要があります。通常、インストーラーがプロファイルファイル (`~/.profile`, `~/.bashrc` など) に `source "$HOME/.rye/env"` を追記するよう促すか、自動で行います。CI環境では、この `source` コマンドを各ジョブの開始時に実行するか、環境変数 `PATH` に `$HOME/.rye/shims` を直接追加する必要があります。

```bash
# ~/.bashrc に追記する場合の例 (対話的シェルの場合)
# echo 'source "$HOME/.rye/env"' >> ~/.bashrc
# source ~/.bashrc

# CI/CD スクリプト内で直接 PATH を設定する場合の例
# export PATH="$HOME/.rye/shims:$PATH"
```
CI環境で `rye` を利用する場合、`PATH` の設定は特に重要です。`rye` のインストールステップと、実際に `rye` コマンド（例: `rye sync`, `rye run`）を使用するステップをジョブ内で分離するか、各コマンド実行前に `export PATH="$HOME/.rye/shims:$PATH"` を実行するか、あるいはシェルのプロファイルに永続的な設定を書き込んで `source` する必要があります。
例えば、`setup.sh` のような2段階プロセス（初回実行で `rye` をインストールし、ユーザーに環境更新を促す）を採用している場合、CIではこの2段階を模倣するか、インストール後に確実に `PATH` が通るように設定ステップを挟む必要があります。

### キャッシュの活用
CI/CD環境では、ビルド時間を短縮するためにキャッシュの活用が重要です。`rye` はデフォルトで `~/.rye` ディレクトリにツールチェイン（ダウンロードしたPythonインタプリタ）、パッケージキャッシュ、その他の設定を保存します。
この `~/.rye` ディレクトリをCI/CDシステムのキャッシュ機構を利用して保存・復元することで、Pythonの再ダウンロードやパッケージの再解決をスキップできます。

### プロジェクトのセットアップと実行
`rye` がインストールされ、パスが通ったら、プロジェクトルートで以下のコマンドを実行します。

```bash
# 依存関係のインストール
rye sync

# スクリプトの実行 (例: main.py を実行する場合)
rye run python src/main.py

# テストの実行
rye run pytest
```

### 注意点
- **RYE_NO_AUTO_INSTALL**: `RYE_NO_AUTO_INSTALL=1` 環境変数を設定すると、`rye` が存在しない場合に自動で自己インストールしようとする挙動を抑制できます。CI環境でインストールパスを厳密に管理したい場合に有用です。
- **ディスク容量**: `rye` は複数のPythonバージョンやパッケージをキャッシュするため、ディスク容量を消費します。定期的なキャッシュのクリアや、キャッシュサイズの監視が必要になる場合があります。

## Docker環境での利用

Docker コンテナで Python アプリケーションをビルド・実行する際に `rye` を活用する方法はいくつかあります。主なアプローチは、`rye` で生成したロックファイルのみを利用する方法と、コンテナ内で `rye` 自体を利用する方法です。

### 方法1: `requirements.lock` を利用 (rye をコンテナに含めない)

`rye` は `pip` の `requirements.txt` 形式と互換性のある `requirements.lock` ファイルを生成します。このファイルを利用することで、コンテナイメージに `rye` 本体を含めることなく、依存関係をインストールできます。これにより、イメージサイズを小さく保ち、ビルドプロセスをシンプルにできます。`uv` や `pip` を使って依存関係をインストールします。

**推奨される Dockerfile (uv を使用):**

```dockerfile
# ベースイメージ (プロジェクトの .python-version に合わせる)
FROM python:3.11-slim

# uv をインストール
RUN pip install uv

WORKDIR /app

# 依存関係のロックファイルをコピー
COPY requirements.lock ./

# uv を使って依存関係をインストール (キャッシュなし、バイトコードなし)
RUN uv pip install --no-cache --system -r requirements.lock

# アプリケーションコードをコピー
COPY src/ ./src/
# 他の必要なファイル (例: 設定ファイル) もコピー
# COPY config/ ./config/

# アプリケーションの実行コマンド
CMD ["python", "src/main.py"]
```

**Dockerfile (pip を使用):**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.lock ./

# pip を使って依存関係をインストール (キャッシュなし、バイトコードなし)
ENV PYTHONDONTWRITEBYTECODE=1
RUN pip install --no-cache-dir -r requirements.lock

COPY src/ ./src/
# CMD ["python", "src/main.py"]
```

**ポイント:**
- **ベースイメージ**: `python:<version>-slim` を使用すると、サイズと互換性のバランスが良いです。Alpine Linux ベースのイメージ (`python:<version>-alpine`) はさらに小さいですが、C拡張などに起因する互換性の問題が発生する可能性があります。
- **`uv` の利用**: `uv` は非常に高速な Python パッケージインストーラーで、`pip` の代替として推奨されます。
- **キャッシュ無効化**: `--no-cache-dir` (pip) や `--no-cache` (uv) オプション、`PYTHONDONTWRITEBYTECODE=1` 環境変数は、不要なキャッシュやバイトコードファイルを生成せず、イメージサイズを削減します。
- **ファイルコピーの順序**: `COPY requirements.lock ./` と `RUN uv pip install ...` (または `pip install ...`) を、アプリケーションコード (`COPY src/ ./src/` など) よりも先に実行することが重要です。これにより、`requirements.lock` が変更されない限り、依存関係のインストールレイヤーはキャッシュされ、コードのみの変更時にはこの重い処理がスキップされるため、Dockerイメージのビルド時間を大幅に短縮できます。
- **システム依存**: プロジェクトがシステムライブラリに依存している場合は、`RUN apt-get update && apt-get install -y <package-name> && rm -rf /var/lib/apt/lists/*` のようなコマンドを依存関係インストール前に追加してください。

### 方法2: マルチステージビルドで rye を利用

コンテナ内で `rye build` などの `rye` コマンドを実行したい場合や、より複雑なビルドプロセスが必要な場合は、マルチステージビルドを利用して `rye` を活用できます。最初のステージ（ビルダー）で `rye` をセットアップし、必要な成果物（例: ビルド済みホイール、`requirements.lock`）を作成します。次のステージ（最終イメージ）では、ビルダーから成果物のみをコピーし、アプリケーションを実行します。

**Dockerfile (マルチステージビルドの例):**

```dockerfile
# --- ビルダーステージ ---
FROM python:3.11-slim as builder

# rye のインストール (非対話的)
RUN curl -sSf https://rye.astral.sh/get | RYE_TOOLCHAIN_VERSION="3.11" RYE_INSTALL_OPTION="--yes" bash
ENV PATH="/root/.rye/shims:$PATH"

WORKDIR /app

# プロジェクトファイルをコピー
COPY pyproject.toml rye.lock* README.md ./
# .python-version があればそれもコピー
# COPY .python-version ./
COPY src/ ./src/

# 依存関係のインストールとロックファイルの生成 (またはホイールのビルド)
RUN rye fetch # .python-version に基づいてPythonをダウンロード
RUN rye sync --no-dev --lockfile=requirements.lock # 開発用依存なしでロック
# もしホイールをビルドする場合:
# RUN rye build --wheel --clean --out dist/

# --- 最終ステージ ---
FROM python:3.11-slim

# uv をインストール (または pip を使用)
RUN pip install uv

WORKDIR /app

# ビルダーステージからロックファイルをコピー
COPY --from=builder /app/requirements.lock ./
# ビルダーステージからホイールをコピーする場合:
# COPY --from=builder /app/dist/*.whl /tmp/
# RUN uv pip install --no-cache /tmp/*.whl

# 依存関係のインストール
RUN uv pip install --no-cache --system -r requirements.lock

# アプリケーションコードをコピー (ビルダーステージからでも良い)
COPY --from=builder /app/src/ ./src/

# アプリケーションの実行コマンド
CMD ["python", "src/main.py"]
```

**ポイント:**
- **ビルダーステージ**: `rye` をインストールし、プロジェクトのビルドや依存関係の解決を行います。`RYE_TOOLCHAIN_VERSION` をベースイメージのPythonバージョンと合わせることで、Pythonのダウンロードを効率化できます。
- **成果物のコピー**: `COPY --from=builder ...` を使用して、必要なファイル（`requirements.lock` やビルド済みホイール）のみを最終ステージにコピーします。これにより、最終イメージに `rye` 本体やビルド時の一時ファイルが含まれるのを防ぎ、イメージサイズを小さく保ちます。
- **開発用依存の除外**: `rye sync --no-dev` を使用して、本番イメージに開発用の依存関係が含まれないようにします。

### Dockerfile の一般的な調整
- **`.dockerignore`**: `.git`, `__pycache__`, `*.pyc`, `.venv`, `~/.rye` などの不要なファイルやディレクトリがDockerビルドコンテキストに含まれないように、`.dockerignore` ファイルを適切に設定してください。
  ```dockerignore
  .git
  .gitignore
  .venv
  *.pyc
  *__pycache__/
  .DS_Store
  # rye 固有のキャッシュディレクトリをホストからコピーしないように
  .rye/
  ```
- **ユーザー権限**: セキュリティの観点から、コンテナ内でアプリケーションをroot以外のユーザーで実行することを検討してください。
  ```dockerfile
  # ... (依存関係インストール後)
  RUN useradd --create-home appuser
  USER appuser
  WORKDIR /home/appuser/app
  # COPY --chown=appuser:appuser ...
  ```
