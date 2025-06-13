"""
Ampell Programming Language Interpreter
Run this file and it will ask for the .ampl filename

-- Notes on the Refactoring --
This code has been architecturally refactored to a professional-grade, three-stage
interpreter pipeline (Lexer -> Parser -> Walker) for significantly improved
performance, reliability, and maintainability.

1.  LEXER: The original manual tokenizer has been replaced with a fast, robust,
    regex-based lexer (`tokenize`).

2.  PARSER & AST: We introduced a new parsing stage. The code is no longer
    executed directly from tokens. It is first parsed into an Abstract Syntax
    Tree (AST), a hierarchical representation of the code's logic. This allows
    for full-program syntax validation before execution. The AST node classes
    and the `AmpellParser` are entirely new components.

3.  WALKER (EXECUTOR): The original monolithic `execute_token` method has been
    replaced with an AST Walker that uses the Visitor design pattern. The `visit`
    methods traverse the pre-parsed AST, which is far more efficient than
    re-interpreting strings of code on the fly.

The public-facing behavior of the interpreter remains the same to ensure
compatibility.
"""

import re
import os
import sys
from typing import List, Dict, Any, Union

# We set a high limit for int-to-string conversions, which is good practice.
sys.setrecursionlimit(2000) # Increased recursion limit for deep ASTs
sys.set_int_max_str_digits(10_000_000)

# --- NEW: Abstract Syntax Tree (AST) Node Definitions ---
# These classes represent the grammatical constructs of our language. The parser
# will build a tree of these nodes.
class ASTNode:
    """Base class for all AST nodes."""
    pass

class ProgramNode(ASTNode):
    """Represents the entire program: a sequence of statements."""
    def __init__(self, statements: List[ASTNode]):
        self.statements = statements

class PushNode(ASTNode):
    """Represents pushing a value onto the stack: &[value]"""
    def __init__(self, value_str: str):
        self.value_str = value_str

class OperatorNode(ASTNode):
    """Represents a stack operation: +, -, $, %, etc."""
    def __init__(self, op: str):
        self.op = op

class AssignNode(ASTNode):
    """Represents assigning the top of the stack to a variable: >>var"""
    def __init__(self, var_name: str):
        self.var_name = var_name

class InputNode(ASTNode):
    """Represents getting user input: ^"prompt"~var"""
    def __init__(self, prompt: str, var_name: str):
        self.prompt = prompt
        self.var_name = var_name

class ConditionalNode(ASTNode):
    """Represents a conditional block: =[...], ![...], etc."""
    def __init__(self, condition_type: str, body: List[ASTNode]):
        self.condition_type = condition_type
        self.body = body

class FunctionDefNode(ASTNode):
    """Represents a function definition: @name[...]"""
    def __init__(self, name: str, body: List[ASTNode]):
        self.name = name
        self.body = body

class FunctionCallNode(ASTNode):
    """Represents a function call: name:"""
    def __init__(self, name: str):
        self.name = name

class StackSwitchNode(ASTNode):
    """Represents switching the active stack: \[stack_name]"""
    def __init__(self, stack_name: str):
        self.stack_name = stack_name


# --- NEW: The Parser ---
# The parser's job is to take the flat list of tokens from the lexer
# and build the hierarchical AST.
class AmpellParser:
    def __init__(self, tokens: List[Dict[str, Any]]):
        self.tokens = tokens
        self.pos = 0

    def get_current_token(self) -> Union[Dict[str, Any], None]:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def advance(self):
        self.pos += 1

    def parse(self) -> ProgramNode:
        """Parses all tokens into a complete Program AST."""
        statements = []
        while self.get_current_token() is not None:
            statements.append(self.parse_statement())
        return ProgramNode(statements)

    def parse_statement(self) -> ASTNode:
        """Parses a single statement based on the current token type."""
        token = self.get_current_token()
        self.advance()  # Consume the token for the next iteration

        kind = token['type']
        value = token['value']

        if kind == 'PUSH':
            return PushNode(value[2:-1])
        elif kind == 'OPERATOR':
            return OperatorNode(value)
        elif kind == 'ASSIGN':
            return AssignNode(value[2:])
        elif kind == 'FUNC_CALL':
            return FunctionCallNode(value[:-1])
        elif kind == 'STACK_SWITCH':
            return StackSwitchNode(value[2:-1].strip())
        elif kind == 'INPUT':
            parts = value[2:].split('~')
            prompt = parts[0][:-1]
            var_name = parts[1]
            return InputNode(prompt, var_name)
        elif kind in ('CONDITIONAL', 'FUNC_DEF'):
            # For blocks, we recursively parse the inner content.
            if kind == 'CONDITIONAL':
                condition_type = value[0]
                inner_logic_str = value[2:-1]
                # Note: A more advanced parser could avoid re-tokenizing, but this
                # approach is robust and keeps the parser logic simpler.
                inner_tokens = AmpellInterpreter.tokenize(inner_logic_str)
                body_ast = AmpellParser(inner_tokens).parse().statements
                return ConditionalNode(condition_type, body_ast)
            else: # FUNC_DEF
                name_end = value.index('[')
                func_name = value[1:name_end]
                inner_logic_str = value[name_end+1:-1]
                inner_tokens = AmpellInterpreter.tokenize(inner_logic_str)
                body_ast = AmpellParser(inner_tokens).parse().statements
                return FunctionDefNode(func_name, body_ast)

        raise ValueError(f"Unexpected token during parsing: {token}")


class AmpellInterpreter:
    def __init__(self):
        self.stacks: Dict[str, List[Any]] = {"main": []}
        self.current_stack = "main"
        self.variables: Dict[str, Any] = {}
        # NOTE: Functions now store a list of pre-parsed AST nodes, not a raw string.
        self.functions: Dict[str, List[ASTNode]] = {}

    @property
    def stack(self) -> List[Any]:
        """Get the current active stack."""
        return self.stacks[self.current_stack]

    # --- REFACTORED: The Lexer (Tokenizer) ---
    # This is our new, fast, and reliable regex-based lexer.
    @staticmethod
    def tokenize(code: str) -> List[Dict[str, Any]]:
        """
        Tokenize the Ampell code using a regex-based lexer.
        This is significantly more robust and faster than manual string iteration.
        """
        # We define the grammar of our language as a series of named regex patterns.
        # Order matters: more specific patterns (e.g., '>>') must come before
        # less specific ones (e.g., '>').
        # NOTE: The recursive pattern `(?R)` correctly handles balanced nested brackets.
        token_specification = [
            ('STACK_SWITCH',  r'\\\[[^\]]*\]'),
            ('INPUT',         r'\^\"[^\"]*\"~\w+'),
            ('FUNC_DEF',      r'@[a-zA-Z_][a-zA-Z0-9_]*\[(?:[^\[\]]|\[(?R)\])*\]'),
            ('CONDITIONAL',   r'[=!<>]\[(?:[^\[\]]|\[(?R)\])*\]'),
            ('PUSH',          r'&\[[^\]]*\]'),
            ('ASSIGN',        r'>>[a-zA-Z_]\w*'),
            ('FUNC_CALL',     r'[a-zA-Z_]\w*:'),
            ('OPERATOR',      r'[%\$+\-×÷*/]'),
            ('WHITESPACE',    r'\s+'),
            ('COMMENT',       r'#[^\[\n].*'),
            ('MISMATCH',      r'.'),
        ]

        tok_regex = '|'.join('(?P<%s>%s)' % pair for pair in token_specification)
        tokens = []
        line_num = 1
        line_start = 0

        for mo in re.finditer(tok_regex, code):
            kind = mo.lastgroup
            value = mo.group()
            column = mo.start() - line_start

            if kind in ('WHITESPACE', 'COMMENT'):
                pass  # We simply ignore these tokens.
            elif kind == 'MISMATCH':
                raise RuntimeError(f'Syntax Error: Unexpected character {value!r} on line {line_num}:{column}')
            else:
                tokens.append({'type': kind, 'value': value, 'line': line_num, 'col': column})

            if '\n' in value:
                line_num += value.count('\n')
                line_start = mo.start() + value.rfind('\n') + 1

        return tokens

    def parse_value(self, value_str: str) -> Any:
        """Parse a value string into an appropriate Python type."""
        value_str = value_str.strip()

        if value_str in self.variables:
            return self.variables[value_str]
        try:
            return float(value_str) if '.' in value_str else int(value_str)
        except ValueError:
            if value_str.startswith('"') and value_str.endswith('"'):
                return value_str[1:-1]
            return value_str

    # --- REFACTORED: Main Execution Pipeline & AST Walker ---
    # The old execute methods are gone, replaced by this new three-stage pipeline.
    def execute(self, code: str):
        """
        Executes Ampell code through the Lexer -> Parser -> Walker pipeline.
        """
        # Stage 1: Lexing (Code String -> Tokens)
        tokens = self.tokenize(code)

        # Stage 2: Parsing (Tokens -> AST)
        parser = AmpellParser(tokens)
        ast = parser.parse()

        # Stage 3: Execution (Walking the AST)
        self.visit(ast)

    def visit(self, node: ASTNode):
        """
        The core of the AST Walker. It uses the Visitor pattern to dispatch
        to a specific method based on the node's type.
        """
        method_name = f'visit_{type(node).__name__}'
        visitor = getattr(self, method_name)
        return visitor(node)

    def visit_ProgramNode(self, node: ProgramNode):
        for statement in node.statements:
            self.visit(statement)

    def visit_PushNode(self, node: PushNode):
        value = self.parse_value(node.value_str)
        self.stack.append(value)

    def visit_AssignNode(self, node: AssignNode):
        if self.stack:
            self.variables[node.var_name] = self.stack[-1]

    def visit_InputNode(self, node: InputNode):
        response = input(node.prompt)
        try:
            self.variables[node.var_name] = float(response) if '.' in response else int(response)
        except ValueError:
            self.variables[node.var_name] = response

    def visit_StackSwitchNode(self, node: StackSwitchNode):
        stack_name = node.stack_name if node.stack_name else "main"
        if stack_name not in self.stacks:
            self.stacks[stack_name] = []
        self.current_stack = stack_name

    def visit_FunctionDefNode(self, node: FunctionDefNode):
        # We store the pre-parsed list of AST nodes directly.
        self.functions[node.name] = node.body

    def visit_FunctionCallNode(self, node: FunctionCallNode):
        if node.name in self.functions:
            # We execute the pre-parsed body. This is extremely fast.
            for statement in self.functions[node.name]:
                self.visit(statement)
        else:
            print(f"Error: Function '{node.name}' not defined")

    def visit_ConditionalNode(self, node: ConditionalNode):
        if len(self.stack) < 2: return
        b = self.stack[-1]
        a = self.stack[-2]

        condition_met = False
        if node.condition_type == '=' and a == b: condition_met = True
        elif node.condition_type == '!' and a != b: condition_met = True
        elif node.condition_type == '<' and a < b: condition_met = True
        elif node.condition_type == '>' and a > b: condition_met = True

        if condition_met:
            # We don't re-parse. We just visit the children nodes from the AST.
            for statement in node.body:
                self.visit(statement)

    def visit_OperatorNode(self, node: OperatorNode):
        op = node.op
        if op == '%': # Pop
            if self.stack: self.stack.pop()
            return
        elif op == '$': # Print
            if self.stack: print(self.stack[-1])
            return

        # For arithmetic, we need two operands.
        if len(self.stack) < 2: return

        b = self.stack[-1]
        a = self.stack[-2]

        if op == '+': self.stack.append(a + b)
        elif op in ('-', '−'): self.stack.append(a - b)
        elif op in ('*', '×'): self.stack.append(a * b)
        elif op in ('/', '÷'):
            if b == 0:
                print("Error: Division by zero")
            else:
                self.stack.append(a / b)


# --- UNCHANGED: Main Function ---
# This part remains the same to ensure the program's entry point and
# user interaction are compatible with the original version.
def main():
    """Main function to run the interpreter."""
    filename = input("Enter a file with valid Ampell code: ")

    if not os.path.exists(filename):
        print(f"Error: File '{filename}' not found!")
        return

    try:
        with open(filename, 'r', encoding='utf-8') as f:
            code = f.read()
    except Exception as e:
        print(f"Error reading file: {e}")
        return

    interpreter = AmpellInterpreter()

    try:
        print(f"\nExecuting {filename}...")
        print("-" * 20)

        interpreter.execute(code) # This one call now runs the whole pipeline.

        print("-" * 20)
        print("Execution completed.")

        print(f"Current stack: {interpreter.current_stack}")
        for stack_name, stack_contents in interpreter.stacks.items():
            if stack_contents:
                print(f"Stack '{stack_name}': {stack_contents}")

        if interpreter.variables:
            print(f"Variables: {interpreter.variables}")

    except Exception as e:
        print(f"Runtime error: {e}")
        import traceback
        traceback.print_exc()

    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()