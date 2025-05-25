#!/usr/bin/env python3
"""
Ampell Programming Language Interpreter
Run this file and it will ask for the .ampl filename
"""

import re
import os
from typing import List, Dict, Any, Union

class AmpellInterpreter:
    def __init__(self):
        self.stacks: Dict[str, List[Any]] = {"main": []}
        self.current_stack = "main"
        self.variables: Dict[str, Any] = {}
        self.functions: Dict[str, str] = {}
    
    @property
    def stack(self) -> List[Any]:
        """Get the current active stack"""
        return self.stacks[self.current_stack]
        
    def tokenize(self, code: str) -> List[str]:
        """Tokenize the Ampell code into individual tokens"""
        # Remove comments (everything after # that's not an else statement or stack switch)
        lines: List[str] = []
        for line in code.split('\n'):
            if '#' in line and not line.strip().startswith('#[') and not line.strip().startswith('\\['):
                line = line.split('#')[0]
            lines.append(line)
        
        code = '\n'.join(lines)
        
        tokens: list[str, int] = []
        i = 0
        while i < len(code):
            # Skip whitespace
            if code[i].isspace():
                i += 1
                continue
            
            # Stack switch command
            if code[i:i+2] == '\\[':
                start = i
                i += 2
                while i < len(code) and code[i] != ']':
                    i += 1
                if i < len(code):
                    i += 1  # Include closing bracket
                tokens.append(code[start:i])
            
            # Input statement
            elif code[i:i+2] == '^"':
                end_quote = code.find('"', i+2)
                tilde_pos = code.find('~', end_quote)
                var_end = tilde_pos + 1
                while var_end < len(code) and (code[var_end].isalnum() or code[var_end] == '_'):
                    var_end += 1
                tokens.append(code[i:var_end])
                i = var_end
            
            # Function definition or conditional with nested brackets
            elif code[i] in '@=!<>' or (code[i:i+2] == '>>'):
                if code[i:i+2] == '>>':
                    # Variable assignment
                    start = i
                    i += 2
                    while i < len(code) and (code[i].isalnum() or code[i] == '_'):
                        i += 1
                    tokens.append(code[start:i])
                else:
                    # Function or conditional - need to handle nested brackets
                    start = i
                    if code[i] == '@':
                        # Function definition
                        while i < len(code) and code[i] != '[':
                            i += 1
                    else:
                        # Conditional
                        i += 1
                    
                    if i < len(code) and code[i] == '[':
                        bracket_count = 1
                        i += 1
                        while i < len(code) and bracket_count > 0:
                            if code[i] == '[':
                                bracket_count += 1
                            elif code[i] == ']':
                                bracket_count -= 1
                            i += 1
                    
                    tokens.append(code[start:i])
            
            # Push value
            elif code[i] == '&' and i+1 < len(code) and code[i+1] == '[':
                start = i
                i += 2
                bracket_count = 1
                while i < len(code) and bracket_count > 0:
                    if code[i] == '[':
                        bracket_count += 1
                    elif code[i] == ']':
                        bracket_count -= 1
                    i += 1
                tokens.append(code[start:i])
            
            # Function call
            elif code[i].isalpha() or code[i] == '_':
                start = i
                while i < len(code) and (code[i].isalnum() or code[i] == '_'):
                    i += 1
                if i < len(code) and code[i] == ':':
                    i += 1
                    tokens.append(code[start:i])
                else:
                    i = start + 1
            
            # Single character tokens
            elif code[i] in '%$+−×÷-*/':
                tokens.append(code[i])
                i += 1
            
            else:
                i += 1
        
        return tokens
    
    def parse_value(self, value_str: str) -> Any:
        """Parse a value string into appropriate Python type"""
        value_str = value_str.strip()
        
        # Check if it's a variable
        if value_str in self.variables:
            return self.variables[value_str]
        
        # Check if it's a number
        try:
            if '.' in value_str:
                return float(value_str)
            else:
                return int(value_str)
        except ValueError:
            pass
        
        # Check if it's a quoted string
        if value_str.startswith('"') and value_str.endswith('"'):
            return value_str[1:-1]
        
        # Return as string if nothing else matches
        return value_str
    
    def execute_logic_block(self, logic: str):
        """Execute a block of logic code"""
        if not logic.strip():
            return
            
        tokens = self.tokenize(logic)
        for token in tokens:
            self.execute_token(token)
    
    def execute_token(self, token: str):
        """Execute a single token"""
        # Stack switch command
        if token.startswith('\\[') and token.endswith(']'):
            stack_name = token[2:-1].strip()
            if not stack_name:
                stack_name = "main"
            
            # Create stack if it doesn't exist
            if stack_name not in self.stacks:
                self.stacks[stack_name] = []
            
            self.current_stack = stack_name
            return
        
        # Push value onto stack
        if token.startswith('&[') and token.endswith(']'):
            value_str = token[2:-1]
            value = self.parse_value(value_str)
            self.stack.append(value)
        
        # Input from user
        elif token.startswith('^"') and '~' in token:
            parts = token[2:].split('~')
            question = parts[0][:-1]  # Remove closing quote
            var_name = parts[1]
            response = input(question)
            # Try to convert to number if possible
            try:
                if '.' in response:
                    response = float(response)
                else:
                    response = int(response)
            except ValueError:
                pass  # Keep as string
            self.variables[var_name] = response
        
        # Remove top of stack
        elif token == '%':
            if self.stack:
                self.stack.pop()
        
        # Print top of stack
        elif token == '$':
            if self.stack:
                print(self.stack[-1])
        
        # Store top of stack in variable
        elif token.startswith('>>'):
            var_name = token[2:]
            if self.stack:
                self.variables[var_name] = self.stack[-1]
        
        # Arithmetic operations (peek, don't pop)
        elif token == '+':
            if len(self.stack) >= 2:
                b = self.stack[-1]
                a = self.stack[-2]
                result = a + b
                self.stack.append(result)
        
        elif token == '-' or token == '−':
            if len(self.stack) >= 2:
                b = self.stack[-1]
                a = self.stack[-2]
                result = a - b
                self.stack.append(result)
        
        elif token == '×' or token == '*':
            if len(self.stack) >= 2:
                b = self.stack[-1]
                a = self.stack[-2]
                result = a * b
                self.stack.append(result)
        
        elif token == '÷' or token == '/':
            if len(self.stack) >= 2:
                b = self.stack[-1]
                a = self.stack[-2]
                if b != 0:
                    result = a / b
                    self.stack.append(result)
                else:
                    print("Error: Division by zero")
        
        # Conditional statements
        elif token.startswith('=[') and token.endswith(']'):
            logic = token[2:-1]
            if len(self.stack) >= 2:
                b = self.stack[-1]
                a = self.stack[-2]
                if a == b:
                    self.execute_logic_block(logic)
        
        elif token.startswith('![') and token.endswith(']'):
            logic = token[2:-1]
            if len(self.stack) >= 2:
                b = self.stack[-1]
                a = self.stack[-2]
                if a != b:
                    self.execute_logic_block(logic)
        
        elif token.startswith('<[') and token.endswith(']'):
            logic = token[2:-1]
            if len(self.stack) >= 2:
                b = self.stack[-1]
                a = self.stack[-2]
                if a < b:
                    self.execute_logic_block(logic)
        
        elif token.startswith('>[') and token.endswith(']'):
            logic = token[2:-1]
            if len(self.stack) >= 2:
                b = self.stack[-1]
                a = self.stack[-2]
                if a > b:
                    self.execute_logic_block(logic)
        
        # Function definition
        elif token.startswith('@') and '[' in token and token.endswith(']'):
            func_name = token[1:token.index('[')]
            logic = token[token.index('[')+1:-1]
            self.functions[func_name] = logic
        
        # Function call
        elif token.endswith(':'):
            func_name = token[:-1]
            if func_name in self.functions:
                self.execute_logic_block(self.functions[func_name])
            else:
                print(f"Error: Function '{func_name}' not defined")
    
    def execute(self, code: str):
        """Execute Ampell code"""
        tokens = self.tokenize(code)
        i = 0
        while i < len(tokens):
            token = tokens[i]
            
            # Handle else statements
            if token.startswith('#[') and token.endswith(']'):
                # This is an else block - only execute if previous condition was false
                # For now, we'll skip else implementation as it requires more complex parsing
                pass
            else:
                self.execute_token(token)
            i += 1

def main():
    sys.set_int_max_str_digits(100000)
    # Ask for filename
    filename = input("Enter the a file with valid Ampell code: ")
    
    # Check if file exists
    if not os.path.exists(filename):
        print(f"Error: File '{filename}' not found!")
        return
    
    # Read the file
    try:
            f = open(filename, 'r', encoding='utf-8')
            code = f.read()
    except Exception as e:
        print(f"Error reading file: {e}")
        return
    
    # Create interpreter and execute
    interpreter = AmpellInterpreter()
    
    try:
        print(f"\nExecuting {filename}...")
        print("-" * 20)
        
        interpreter.execute(code)
        print("-" * 20)
        print("Execution completed.")
        
        # Show final state of all stacks
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
    
    # Keep window open
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()
