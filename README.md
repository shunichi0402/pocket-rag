# Pocket RAG

Pocket RAGは、Markdown文書を分割・埋め込み・検索できるRAG（Retrieval-Augmented Generation）システムです。  
PLaMo埋め込みモデルとChatGPT APIを活用し、ベクトル検索・キーワード検索・ハイブリッド検索が可能です。

## 主な機能

- Markdownファイルの分割・埋め込み・DB登録
- プロジェクト単位での文書管理
- ベクトル検索（意味検索）
- キーワード検索（ChatGPTによるキーワード抽出）
- ベクトル＋キーワードのハイブリッド検索
- ドキュメントの追加・削除

## 使い方

### 1. セットアップ

- Python 3.10以上推奨

- **プロジェクトのセットアップ**:
  以下のコマンドを実行してセットアップスクリプトを実行します。
  ```bash
  ./setup.sh
  ```
  スクリプトは最初に `rye`（プロジェクト管理ツール）がインストールされているか確認します。
  もし `rye` がインストールされていない場合、スクリプトは `rye` をインストールし、シェル環境を更新（シェルを再起動するか `source \$HOME/.rye/env` を実行）してから、再度 `./setup.sh` を実行するよう指示します。
  `rye` が既にセットアップされていれば、スクリプトはプロジェクトの依存関係をインストールします。

### 2. サンプルコード

```python
from pocket_rag import RAG

# RAGインスタンス生成（DBディレクトリ指定）
rag = RAG("./database")

# プロジェクト追加
rag.add_project("test", name="テストプロジェクト", description="サンプルで使用するテストプロジェクトです。")

# プロジェクト取得
project = rag.get_project(project_id="test")[0]

# ドキュメント追加（Markdownファイルを分割・埋め込みDB登録）
project.add_document(path="./test.md", type="markdown")

# ベクトル検索
vector_results = project.search_by_vector("坂本龍馬について教えてください", k=3)

# キーワード検索
keyword_results = project.search_by_keyword("坂本龍馬について教えてください")

# ハイブリッド検索
hybrid_results = project.search_hybrid("坂本龍馬について教えてください", k=3)

# ドキュメント削除
project.remove_document(document_id=1)

# プロジェクトの削除
rag.remove_project("test")
```

### 3. サンプル

- サンプルスクリプト実行
  ```
  python sample.py
  ```

- 検索結果は `result.json` に出力されます。

## 注意事項

- OpenAI APIキーが必要です（.envで設定）。
- PLaMo埋め込みモデルのダウンロードには時間がかかる場合があります。
- ドキュメントの登録時に埋め込みやLLMによる文章整理を行うので、時間がかかる場合があります。
- SQLite3を利用しています。