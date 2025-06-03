#!/bin/bash

# rye がインストールされているか確認
if ! command -v rye &> /dev/null
then
    echo "rye がインストールされていません。インストールを開始します..."
    curl -sSf https://rye.astral.sh/get | RYE_INSTALL_OPTION="--yes" bash
    echo "" # 改行のため
    echo "rye のインストールが完了しました。"
    source "$HOME/.rye/env"
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
