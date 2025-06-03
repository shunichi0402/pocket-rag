#!/bin/bash

# rye がインストールされているか確認
if ! command -v rye &> /dev/null
then
    echo "rye がインストールされていません。インストールを開始します..."
    curl -sSf https://rye.astral.sh/get | bash -s -- --yes
    echo "" # 改行のため
    echo "rye のインストールが完了しました。"
    echo "変更を有効にするために、現在のシェルを再起動するか、以下のコマンドを実行してください:"
    echo "  source \"\$HOME/.rye/env\""
    echo "その後、再度 ./setup.sh を実行してください。"
    exit 0
else
    echo "rye は既にインストールされています。"
fi

# プロジェクトの依存関係をインストールします
echo "プロジェクトの依存関係をインストールしています..."
rye sync

# 環境変数の設定
# このプロジェクトでは OpenAI API を利用します。
# OPENAI_API_KEY を環境変数に設定してください。
# .env ファイルを作成し、以下のように記述してください:
# OPENAI_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
#
# .env ファイルの例:
# echo "OPENAI_API_KEY="YOUR_API_KEY_HERE"" > .env
# echo ".env ファイルが作成されました。APIキーを設定してください。"

echo "セットアップが完了しました。"
