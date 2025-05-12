from dotenv import load_dotenv
load_dotenv()

# from pocket_rag.embedding import Embedding
import mistune

# embedding = Embedding()

test_text = """
# RAGシステム テスト用サンプルテキスト

このドキュメントは、Retrieval Augmented Generation (RAG) システムのテストを目的として作成されました。様々な分野の情報を構造化されたMarkdown形式で含んでいます。

## セクション 1: 歴史と地理

日本に関する基本的な歴史および地理情報を提供します。


### 日本の地理

日本は、ユーラシア大陸の東端、太平洋の西に位置する島国です。北緯20度から45度にかけて、南北におよそ3,000キロメートルにわたって細長く延びています。領土は、北海道、本州、四国、九州という四つの主要な島を中心に、伊豆・小笠原諸島、南西諸島（琉球諸島）など、6,800以上の島々で構成されており、総面積は約37.8万平方キロメートルです。

日本の地理を特徴づける最大の要素は、その起伏に富んだ地形です。国土の約7割から8割が山地や丘陵で占められており、広大な平野は少ないのが特徴です。本州の中央部には「日本の屋根」とも称される飛騨山脈、木曽山脈、赤石山脈といった日本アルプスが連なり、標高3,000メートル級の山々がそびえています。また、日本列島は環太平洋造山帯の一部にあたり、多数の活火山が存在します。日本最高峰の富士山（標高3,776m）は、その美しい姿とともに日本の象徴となっています。活発な火山活動は温泉などの恵みをもたらす一方で、地震も非常に多く発生する地域であり、日本列島は複数のプレートの境界に位置するため、常に地震のリスクにさらされています。

気候もまた、南北に長い国土のため地域によって大きく異なります。ケッペンの気候区分で見ると、北海道の一部は亜寒帯、多くの地域は温帯に属し、南西諸島は亜熱帯気候となっています。四季の変化が明瞭で、春は桜、夏は緑、秋は紅葉、冬は雪景色と、季節ごとの美しい自然景観が見られます。太平洋側は夏に高温多湿で冬は比較的乾燥し晴天が多い傾向があるのに対し、日本海側は冬に北西からの季節風の影響で多量の雪が降る豪雪地帯が多いのが特徴です。また、夏から秋にかけては台風が接近・上陸しやすく、大雨や強風による自然災害が発生しやすいといった側面も持ち合わせています。梅雨期には多くの地域で雨が降り続きます。

河川は山がちな地形のため、一般的に流れが速く、長さも短い傾向があります。信濃川や利根川などが比較的長い河川ですが、世界的基準では短い部類に入ります。河川は古くから農業用水や生活用水として利用されてきましたが、急峻な地形は水害のリスクも高く、治水事業が重要な課題となってきました。湖沼も点在しており、琵琶湖は日本最大の面積を誇る湖です。

四方を海に囲まれた日本では、複雑な海岸線も特徴の一つです。特にリアス式海岸は三陸海岸や若狭湾などで見られ、天然の良港を形成し漁業や港湾として利用されています。温暖な黒潮と冷たい親潮が日本近海でぶつかる潮目では、多様な魚介類が豊富に生息しており、日本の豊かな漁業を支えています。

このような多様な地理的環境は、日本の社会や経済に大きな影響を与えています。限られた平野部に人口や産業が集中し、太平洋ベルトのような工業地帯が形成されました。山地が多く平野が少ない地形は、古くから米作を中心とした農業の形態に影響を与え、また交通網の整備（特に山間部のトンネルや橋、新幹線網など）において技術的な課題を乗り越える必要を生じさせました。多様な自然は観光資源としても重要であり、国立公園や世界自然遺産などに指定されている地域も多くあります。一方で、地震や火山活動、台風、豪雨といった自然災害への備えは、日本の社会において常に重要な課題であり続けています。

* **首都**: 東京
* **面積**: 約377,975平方キロメートル
* **人口**: 約1億2500万人（概算、変動します）
* **主要な島**: 北海道、本州、四国、九州

### 歴史上の出来事

日本の歴史における重要な出来事の一つに**明治維新**があります。これは1868年に起こり、日本の近代化の端緒となりました。この時代に活躍した人物として、**坂本龍馬**などが知られています。

> 「新しい時代が始まる。」
> ― 坂本龍馬（とされる言葉の一つ）

## セクション 2: 科学と技術

基本的な科学の法則と、一般的なプログラミング言語に関する情報を含みます。

### 物理学の基本

**ニュートンの第一法則**（慣性の法則）は、「物体は外部から力を加えられない限り、静止している物体は静止し続け、運動している物体は等速直線運動を続ける」というものです。

### 化学の基本

水の化学式は $H_2O$ です。これは水素原子2つと酸素原子1つから構成されることを示しています。

### プログラミングについて

*Python* は、汎用性の高い人気のあるプログラミング言語です。シンプルで読みやすい構文が特徴です。

```python
# Pythonでの簡単な変数宣言と出力の例
greeting = "こんにちは、世界！"
print(greeting)
```
"""

convert_rst = mistune.create_markdown(renderer="ast")
ast = convert_rst(test_text)

# print(ast)

def node_to_markdown(node):
    if node["type"] == "text":
        return node["raw"]
    elif node["type"] == "strong":
        return "**" + "".join(node_to_markdown(child) for child in node.get("children", [])) + "**"
    elif node["type"] == "block_text":
        return "".join(node_to_markdown(child) for child in node.get("children", []))
    elif node["type"] == "list_item":
        return "* " + "".join(node_to_markdown(child) for child in node.get("children", []))
    elif node["type"] == "paragraph":
        return "".join(node_to_markdown(child) for child in node.get("children", []))
    # 必要に応じて他のノード型も追加
    return ""

def handle_heading(node, stack, tree):
    level = node["attrs"]["level"]
    text = ""
    if node["children"] and node["children"][0]["type"] == "text":
        text = node["children"][0]["raw"]
    while stack and stack[-1]["level"] >= level:
        stack.pop()
    item = {"type": "heading", "text": text, "level": level, "children": []}
    if stack:
        stack[-1]["children"].append(item)
    else:
        tree.append(item)
    stack.append(item)

def handle_paragraph(node, stack, tree):
    texts = []
    for child in node.get("children", []):
        if child["type"] == "text":
            texts.append(child["raw"])
    para_text = "".join(texts)
    item = {"text": para_text, "children": []}
    if stack:
        stack[-1]["children"].append(item)
    else:
        tree.append(item)

def handle_block_quote(node, stack, tree):
    texts = []
    for child in node.get("children", []):
        if child["type"] == "paragraph":
            for gchild in child.get("children", []):
                if gchild["type"] == "text":
                    texts.append(gchild["raw"])
    quote_text = "\n".join(texts)
    quote_md = "> " + quote_text.replace("\n", "\n> ")
    item = {"text": quote_md, "children": []}
    if stack:
        stack[-1]["children"].append(item)
    else:
        tree.append(item)

def handle_list(node, stack, tree):
    items = []
    for li in node.get("children", []):
        li_text = node_to_markdown(li)
        items.append({"text": li_text, "children": []})
    item = {"children": items}
    if stack:
        stack[-1]["children"].append(item)
    else:
        tree.append(item)

def handle_block_code(node, stack, tree):
    code = node.get("raw", "")
    info = node.get("info", "")
    if info:
        code_md = f"```{info}\n{code}\n```"
    else:
        code_md = f"```\n{code}\n```"
    item = {"text": code_md, "children": []}
    if stack:
        stack[-1]["children"].append(item)
    else:
        tree.append(item)

def build_tree(ast):
    tree = []
    stack = []
    handlers = {
        "heading": handle_heading,
        "paragraph": handle_paragraph,
        "block_quote": handle_block_quote,
        "list": handle_list,
        "block_code": handle_block_code,
    }
    for node in ast:
        handler = handlers.get(node["type"])
        if handler:
            handler(node, stack, tree)
    return tree


def print_tree(nodes, level=0):
    indent = "  " * level
    for node in nodes:
        if "text" in node:
            print(f"{indent}{node['text']}")
        # childrenがあれば再帰
        if "children" in node:
            print_tree(node["children"], level + 1)

tree = build_tree(ast)
print(tree)
# print_tree(tree)
