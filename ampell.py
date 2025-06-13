#!/usr/bin/env python3
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

-- FIX 2024-06-13 --
* REMOVED: The recursive regex pattern `(?R)` which caused a `re.error` as it is not
    supported by Python's standard `re` module.
* REFACTORED: The Lexer and Parser. The Lexer now produces simpler tokens for block
    constructs (e.g., `FUNC_DEF_INTRO`, `L_BRACKET`).
* ENHANCED: The Parser is now a proper recursive descent parser, responsible for
    building nested structures by tracking `L_BRACKET` and `R_BRACKET` tokens. This is
    a more robust and compatible method for handling nested code blocks.
"""

import re
import os
import sys
from typing import List, Dict, Any, Union

# We set a high limit for int-to-string conversions, which is good practice.
sys.setrecursionlimit(2000)
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
    r"""Represents pushing a value onto the stack: &[value]"""
    def __init__(self, value_str: str):
        self.value_str = value_str

class OperatorNode(ASTNode):
    """Represents a stack operation: +, -, $, %, etc."""
    def __init__(self, op: str):
        self.op = op

class AssignNode(ASTNode):
    r"""Represents assigning the top of the stack to a variable: >>var"""
    def __init__(self, var_name: str):
        self.var_name = var_name

class InputNode(ASTNode):
    r"""Represents getting user input: ^"prompt"~var"""
    def __init__(self, prompt: str, var_name: str):
        self.prompt = prompt
        self.var_name = var_name

class ConditionalNode(ASTNode):
    r"""Represents a conditional block: =[...], ![...], etc."""
    def __init__(self, condition_type: str, body: List[ASTNode]):
        self.condition_type = condition_type
        self.body = body

class FunctionDefNode(ASTNode):
    r"""Represents a function definition: @name[...]"""
    def __init__(self, name: str, body: List[ASTNode]):
        self.name = name
        self.body = body

class FunctionCallNode(ASTNode):
    r"""Represents a function call: name:"""
    def __init__(self, name: str):
        self.name = name

class StackSwitchNode(ASTNode):
    r"""Represents switching the active stack: \[stack_name]"""
    def __init__(self, stack_name: str):
        self.stack_name = stack_name


# --- NEW & REFACTORED: The Parser ---
# The parser's job is to take the flat list of tokens from the lexer
# and build the hierarchical AST. It now correctly handles nested structures.
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
        # We parse statements until we run out of tokens or hit a closing bracket
        # (which is handled by a recursive call).
        while self.get_current_token() is not None and self.get_current_token()['type'] != 'R_BRACKET':
            statements.append(self.parse_statement())
        return ProgramNode(statements)

    def parse_statement(self) -> ASTNode:
        """Parses a single statement based on the current token type."""
        token = self.get_current_token()
        kind = token['type']
        value = token['value']

        if kind == 'FUNC_DEF_INTRO':
            self.advance() # Consume intro token '@func'
            func_name = value[1:]
            
            # Expect a left bracket
            if not self.get_current_token() or self.get_current_token()['type'] != 'L_BRACKET':
                raise SyntaxError("Expected '[' after function definition")
            self.advance() # Consume '['
            
            # Recursively parse the body
            body_ast = self.parse().statements
            
            # Expect a right bracket
            if not self.get_current_token() or self.get_current_token()['type'] != 'R_BRACKET':
                raise SyntaxError(f"Unclosed function definition for '{func_name}'")
            self.advance() # Consume ']'
            return FunctionDefNode(func_name, body_ast)

        if kind == 'COND_OP':
            self.advance() # Consume operator token '=', '>', etc.
            
            # Expect a left bracket
            if not self.get_current_token() or self.get_current_token()['type'] != 'L_BRACKET':
                raise SyntaxError(f"Expected '[' after conditional operator '{value}'")
            self.advance() # Consume '['
            
            # Recursively parse the body
            body_ast = self.parse().statements

            # Expect a right bracket
            if not self.get_current_token() or self.get_current_token()['type'] != 'R_BRACKET':
                 raise SyntaxError(f"Unclosed conditional block starting with '{value}'")
            self.advance() # Consume ']'
            return ConditionalNode(value, body_ast)

        # For simple, non-nested tokens:
        self.advance() # Consume the current token
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
            
        raise ValueError(f"Unexpected token during parsing: {token}")


class AmpellInterpreter:
    def __init__(self):
        self.stacks: Dict[str, List[Any]] = {"main": []}
        self.current_stack = "main"
        self.variables: Dict[str, Any] = {}
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
        """
        # NOTE: The grammar has been simplified. We no longer try to match whole
        # nested blocks. Instead, we tokenize the opening and closing parts,
        # and the parser handles the nesting logic.
        token_specification = [
            ('PUSH',          r'&\[[^\]]*\]'),
            ('STACK_SWITCH',  r'\\\[[^\]]*\]'),
            ('INPUT',         r'\^\"[^\"]*\"~\w+'),
            ('ASSIGN',        r'>>[a-zA-Z_]\w*'),
            ('FUNC_DEF_INTRO',r'@[a-zA-Z_]\w*'),
            ('FUNC_CALL',     r'[a-zA-Z_]\w*:'),
            ('COND_OP',       r'[=!<>]'), # NOTE: Simplified
            ('L_BRACKET',     r'\['),     # NOTE: New token
            ('R_BRACKET',     r'\]'),     # NOTE: New token
            ('OPERATOR',      r'[%\$+\-×÷*/]'),
            ('WHITESPACE',    r'\s+'),
            ('COMMENT',       r'#[^\[\n].*'),
            ('MISMATCH',      r'.'),
        ]

        tok_regex = '|'.join(f'(?P<{pair[0]}>{pair[1]})' for pair in token_specification)
        tokens = []
        line_num = 1
        line_start = 0

        for mo in re.finditer(tok_regex, code):
            kind = mo.lastgroup
            value = mo.group()
            column = mo.start() - line_start

            if kind in ('WHITESPACE', 'COMMENT'):
                pass
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

    def execute(self, code: str):
        """
        Executes Ampell code through the Lexer -> Parser -> Walker pipeline.
        """
        tokens = self.tokenize(code)
        parser = AmpellParser(tokens)
        ast = parser.parse()
        self.visit(ast)

    # --- REFACTORED: AST Walker (Visitor) ---
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
        self.functions[node.name] = node.body

    def visit_FunctionCallNode(self, node: FunctionCallNode):
        if node.name in self.functions:
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
            for statement in node.body:
                self.visit(statement)

    def visit_OperatorNode(self, node: OperatorNode):
        op = node.op
        if op == '%':
            if self.stack: self.stack.pop()
            return
        elif op == '$':
            if self.stack: print(self.stack[-1])
            return

        if len(self.stack) < 2: return
        # --- THE FIX IS HERE ---
        # We now POP the operands from the stack, consuming them.
        b = self.stack.pop()
        a = self.stack.pop()

        # We compute the result and push ONLY the result back.
        if op == '+':
            self.stack.append(a + b)
        elif op in ('-', '−'):
            self.stack.append(a - b)
        elif op in ('*', '×'):
            self.stack.append(a * b)
        elif op in ('/', '÷'):
            if b == 0:
                print("Error: Division by zero")
                # On error, we should restore the stack to its previous state.
                self.stack.append(a)
                self.stack.append(b)
            else:
                self.stack.append(a / b)

# --- UNCHANGED: Main Function ---
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
        interpreter.execute(code)
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