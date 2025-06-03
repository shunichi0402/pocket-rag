import mistune
from typing import List, Dict, Any, Optional, Callable

import mistune
from typing import List, Dict, Any, Optional, Callable, cast

# Type Aliases
MarkdownAstNode = Dict[str, Any]  # Mistune's AST nodes
CustomTreeNode = Dict[str, Any]  # Custom tree structure nodes
NodeStack = List[CustomTreeNode]
NodeTree = List[CustomTreeNode]
HandlerCallable = Callable[[MarkdownAstNode, NodeStack, NodeTree], None]


def node_to_markdown(node: MarkdownAstNode) -> str:
    """
    ノード（ASTノード）を再帰的にMarkdown文字列へ変換する。

    Args:
        node (MarkdownAstNode): MarkdownのASTノード

    Returns:
        str: ノードをMarkdown形式に変換した文字列
    """
    node_type: str = node.get("type", "")
    raw_content: str = node.get("raw", "")
    children: List[MarkdownAstNode] = node.get("children", [])

    if node_type == "text":
        return raw_content
    elif node_type == "strong":
        return "**" + "".join(node_to_markdown(child) for child in children) + "**"
    elif node_type == "block_text":
        return "".join(node_to_markdown(child) for child in children)
    elif node_type == "list_item":
        # Assuming list_item children are processed to form the item's content
        processed_children: str = "".join(node_to_markdown(child) for child in children)
        # Ensure that the processing of children does not already include the marker
        # Based on common Markdown, list items themselves don't repeat the marker
        # but their content is what follows it.
        # The current code might produce "* * item" if a child also returns "* item".
        # For now, sticking to the original logic.
        return "* " + processed_children
    elif node_type == "paragraph":
        return "".join(node_to_markdown(child) for child in children)
    # 必要に応じて他のノード型も追加
    return ""


def handle_heading(node: MarkdownAstNode, stack: NodeStack, tree: NodeTree) -> None:
    """
    headingノードを処理し、ツリー構造に追加する。

    Args:
        node (MarkdownAstNode): ASTノード（heading）
        stack (NodeStack): 現在のツリーの親ノードのスタック
        tree (NodeTree): ルートノードのリスト

    Returns:
        None
    """
    level: int = node.get("attrs", {}).get("level", 0)
    text: str = ""
    children: List[MarkdownAstNode] = node.get("children", [])
    if children and children[0].get("type") == "text":
        text = "#" * level + " " + children[0].get("raw", "")

    while stack and stack[-1].get("level", float('-inf')) >= level:
        stack.pop()

    item: CustomTreeNode = {"type": "heading", "text": text, "level": level, "children": []}
    if stack:
        stack[-1].setdefault("children", []).append(item)
    else:
        tree.append(item)
    stack.append(item)


def handle_paragraph(node: MarkdownAstNode, stack: NodeStack, tree: NodeTree) -> None:
    """
    paragraphノードを処理し、ツリー構造に追加する。

    Args:
        node (MarkdownAstNode): ASTノード（paragraph）
        stack (NodeStack): 現在のツリーの親ノードのスタック
        tree (NodeTree): ルートノードのリスト

    Returns:
        None
    """
    texts: List[str] = []
    children: List[MarkdownAstNode] = node.get("children", [])
    for child in children:
        if child.get("type") == "text":
            texts.append(child.get("raw", ""))
    para_text: str = "".join(texts)
    item: CustomTreeNode = {"type": "paragraph", "text": para_text, "children": []}
    if stack:
        stack[-1].setdefault("children", []).append(item)
    else:
        tree.append(item)


def handle_block_quote(node: MarkdownAstNode, stack: NodeStack, tree: NodeTree) -> None:
    """
    block_quoteノードを処理し、ツリー構造に追加する。

    Args:
        node (MarkdownAstNode): ASTノード（block_quote）
        stack (NodeStack): 現在のツリーの親ノードのスタック
        tree (NodeTree): ルートノードのリスト

    Returns:
        None
    """
    texts: List[str] = []
    children: List[MarkdownAstNode] = node.get("children", [])
    for child in children:
        if child.get("type") == "paragraph":
            grandchildren: List[MarkdownAstNode] = child.get("children", [])
            for gchild in grandchildren:
                if gchild.get("type") == "text":
                    texts.append(gchild.get("raw", ""))
    quote_text: str = "\n".join(texts)
    quote_md: str = "> " + quote_text.replace("\n", "\n> ")
    item: CustomTreeNode = {"type": "block_quote", "text": quote_md, "children": []}
    if stack:
        stack[-1].setdefault("children", []).append(item)
    else:
        tree.append(item)


def handle_list(node: MarkdownAstNode, stack: NodeStack, tree: NodeTree) -> None:
    """
    listノードを処理し、ツリー構造に追加する。

    Args:
        node (MarkdownAstNode): ASTノード（list）
        stack (NodeStack): 現在のツリーの親ノードのスタック
        tree (NodeTree): ルートノードのリスト

    Returns:
        None
    """
    list_md: str = ""
    list_items: List[MarkdownAstNode] = node.get("children", [])
    for li in list_items:
        # Assuming node_to_markdown correctly handles list_item nodes
        li_text: str = node_to_markdown(li)
        list_md += li_text + "\n" # Original code had list_md = list_md + ...

    item: CustomTreeNode = {"type": "list", "text": list_md.strip(), "children": []}

    if stack:
        stack[-1].setdefault("children", []).append(item)
    else:
        tree.append(item)


def handle_block_code(node: MarkdownAstNode, stack: NodeStack, tree: NodeTree) -> None:
    """
    block_codeノードを処理し、ツリー構造に追加する。

    Args:
        node (MarkdownAstNode): ASTノード（block_code）
        stack (NodeStack): 現在のツリーの親ノードのスタック
        tree (NodeTree): ルートノードのリスト

    Returns:
        None
    """
    code: str = node.get("raw", "")
    info: Optional[str] = node.get("info") # info can be None

    code_md: str
    if info:
        code_md = f"```{info}\n{code}\n```"
    else:
        code_md = f"```\n{code}\n```"

    item: CustomTreeNode = {"type": "block_code", "text": code_md, "children": []}
    if stack:
        stack[-1].setdefault("children", []).append(item)
    else:
        tree.append(item)


def parse_markdown(markdown_text: str) -> List[MarkdownAstNode]:
    """
    MarkdownテキストをAST（抽象構文木）に変換する。

    Args:
        markdown_text (str): Markdown形式のテキスト

    Returns:
        List[MarkdownAstNode]: ASTノードのリスト
    """
    # The exact return type of create_markdown might be complex; using Any for the renderer itself.
    markdown_parser: Any = mistune.create_markdown(renderer="ast")
    # Assuming markdown_parser(markdown_text) returns List[Dict[str, Any]] which is List[MarkdownAstNode]
    # Using cast to assure 'ty' of the type, if it infers str | list[Unknown] from 'Any' callable.
    parsed_result: Any = markdown_parser(markdown_text)
    ast: List[MarkdownAstNode] = cast(List[MarkdownAstNode], parsed_result)
    return ast


def build_tree(markdown_text: str) -> NodeTree:
    """
    Markdownテキストからツリー構造を構築する。

    Args:
        markdown_text (str): Markdown形式のテキスト

    Returns:
        NodeTree: Markdownのツリー構造
    """
    ast: List[MarkdownAstNode] = parse_markdown(markdown_text)

    tree: NodeTree = []
    stack: NodeStack = []

    handlers: Dict[str, HandlerCallable] = {
        "heading": handle_heading,
        "paragraph": handle_paragraph,
        "block_quote": handle_block_quote,
        "list": handle_list,
        "block_code": handle_block_code,
    }

    for node in ast:
        node_type: Optional[str] = node.get("type")
        if node_type:
            handler: Optional[HandlerCallable] = handlers.get(node_type)
            if handler:
                handler(node, stack, tree)

    return tree


def print_tree(nodes: NodeTree, level: int = 0) -> None:
    """
    ツリー構造をインデント付きで標準出力に表示する。

    Args:
        nodes (NodeTree): ツリー構造のノードリスト
        level (int, optional): インデントレベル（デフォルト: 0）

    Returns:
        None
    """
    indent: str = "  " * level
    for node in nodes:
        if "text" in node: # Check if text key exists
            print(f"{indent}{node.get('text', '')}") # Use .get for safety

        children: Optional[NodeTree] = node.get("children") # children might be missing
        if children: # Check if children is not None and not empty (though empty list is fine for recursion)
            print_tree(children, level + 1)
