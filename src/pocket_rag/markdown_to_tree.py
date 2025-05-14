import mistune

def node_to_markdown(node):
    """
    ノード（ASTノード）を再帰的にMarkdown文字列へ変換する。

    Args:
        node (dict): MarkdownのASTノード

    Returns:
        str: ノードをMarkdown形式に変換した文字列
    """
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
    """
    headingノードを処理し、ツリー構造に追加する。

    Args:
        node (dict): ASTノード（heading）
        stack (list): 現在のツリーの親ノードのスタック
        tree (list): ルートノードのリスト

    Returns:
        None
    """
    level = node["attrs"]["level"]
    text = ""
    if node["children"] and node["children"][0]["type"] == "text":
        text = "#" * level + " " + node["children"][0]["raw"]
    while stack and stack[-1]["level"] >= level:
        stack.pop()
    item = {"type": "heading", "text": text, "level": level, "children": []}
    if stack:
        stack[-1]["children"].append(item)
    else:
        tree.append(item)
    stack.append(item)

def handle_paragraph(node, stack, tree):
    """
    paragraphノードを処理し、ツリー構造に追加する。

    Args:
        node (dict): ASTノード（paragraph）
        stack (list): 現在のツリーの親ノードのスタック
        tree (list): ルートノードのリスト

    Returns:
        None
    """
    texts = []
    for child in node.get("children", []):
        if child["type"] == "text":
            texts.append(child["raw"])
    para_text = "".join(texts)
    item = {"type": "paragraph", "text": para_text, "children": []}
    if stack:
        stack[-1]["children"].append(item)
    else:
        tree.append(item)

def handle_block_quote(node, stack, tree):
    """
    block_quoteノードを処理し、ツリー構造に追加する。

    Args:
        node (dict): ASTノード（block_quote）
        stack (list): 現在のツリーの親ノードのスタック
        tree (list): ルートノードのリスト

    Returns:
        None
    """
    texts = []
    for child in node.get("children", []):
        if child["type"] == "paragraph":
            for gchild in child.get("children", []):
                if gchild["type"] == "text":
                    texts.append(gchild["raw"])
    quote_text = "\n".join(texts)
    quote_md = "> " + quote_text.replace("\n", "\n> ")
    item = {"type": "block_quote", "text": quote_md, "children": []}
    if stack:
        stack[-1]["children"].append(item)
    else:
        tree.append(item)

def handle_list(node, stack, tree):
    """
    listノードを処理し、ツリー構造に追加する。

    Args:
        node (dict): ASTノード（list）
        stack (list): 現在のツリーの親ノードのスタック
        tree (list): ルートノードのリスト

    Returns:
        None
    """
    list_md = ""
    for li in node.get("children", []):
        li_text = node_to_markdown(li)
        list_md = list_md + li_text + "\n"
    item = {"type": "list", "text": list_md, "children": []}

    if stack:
        stack[-1]["children"].append(item)
    else:
        tree.append(item)

def handle_block_code(node, stack, tree):
    """
    block_codeノードを処理し、ツリー構造に追加する。

    Args:
        node (dict): ASTノード（block_code）
        stack (list): 現在のツリーの親ノードのスタック
        tree (list): ルートノードのリスト

    Returns:
        None
    """
    code = node.get("raw", "")
    info = node.get("info", "")
    if info:
        code_md = f"```{info}\n{code}\n```"
    else:
        code_md = f"```\n{code}\n```"
    item = {"type": "block_code", "text": code_md, "children": []}
    if stack:
        stack[-1]["children"].append(item)
    else:
        tree.append(item)

def parse_markdown(markdown_text):
    """
    MarkdownテキストをAST（抽象構文木）に変換する。

    Args:
        markdown_text (str): Markdown形式のテキスト

    Returns:
        list: ASTノードのリスト
    """
    convert_rst = mistune.create_markdown(renderer="ast")
    ast = convert_rst(markdown_text)
    return ast

def build_tree(markdown_text):
    """
    Markdownテキストからツリー構造を構築する。

    Args:
        markdown_text (str): Markdown形式のテキスト

    Returns:
        list: Markdownのツリー構造
    """
    ast = parse_markdown(markdown_text)

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
    """
    ツリー構造をインデント付きで標準出力に表示する。

    Args:
        nodes (list): ツリー構造のノードリスト
        level (int, optional): インデントレベル（デフォルト: 0）

    Returns:
        None
    """
    indent = "  " * level
    for node in nodes:
        if "text" in node:
            print(f"{indent}{node['text']}")
        # childrenがあれば再帰
        if "children" in node:
            print_tree(node["children"], level + 1)
