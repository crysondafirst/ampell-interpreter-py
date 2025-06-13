# Ampell Interpreter

Ampell is a simple, powerful stack-based programming language designed for straightforward scripting and algorithmic logic. This project provides a robust, multi-stage interpreter written in Python to execute Ampell code.

This version of Ampell, aims for the esolang to improve it's speed and performance, preferably in the source code.

## Features

-   **Stacks**: A multi-stack environment, allowing for complex data separation.
-   **Variables**: Store and retrieve values dynamically.
-   **Arithmetic**: Destructive operators for intuitive stack-based math.
-   **Conditionals**: Non-destructive (peek-based) conditional logic.
-   **Functions**: Define and call functions, enabling recursion and code reuse.
-   **I/O**: Interact with the user through console input and output.

## Getting Started

### Prerequisites

-   Python 3.x

### Usage

1.  Clone or download the `ampell.py` interpreter script.
2.  Create a text file with your Ampell code (e.g., `my_program.ampl`).
3.  Run the interpreter from your terminal and provide the filename when prompted:
    ```sh
    python ampell.py
    Enter a file with valid Ampell code: my_program.ampl
    ```

---

## Examples

### 1. Hello, World!

The simplest program to print a string.

```ampell
&["Hello, World!"]
$
```

### 2. Simple Arithmetic
Push two numbers, add them, and print the result.
```
# Pushes 15, then 7. The stack is [15, 7]
&[15] &[7]

# The '-' operator pops 7 and 15, calculates 15-7=8, and pushes 8.
-

# The stack is now [8]. The '$' prints the top.
$
# Output: 8
```
### 3. User Input and Conditionals
Ask the user for their age and print a message based on the input.
```
^"What is your age?"~age

&[age] &[18] <[
  &["You are under 18."]$
]

&[age] &[18] =[
  &["You are exactly 18."]$
]

&[age] &[18] >[
  &["You are over 18."]$
]
```
### 4. Recursive Countdown Loop
A more advanced example demonstrating functions, recursion, and stack management.
```
^"Enter a number to count down from"~n
&[n]
@countdown[
    $           # Print the current number on top of the stack.
    &[1]        # Push 1 to subtract with.
    -           # Destructive subtract. Stack now holds (n-1).
    &[0]        # Push 0 for comparison. Stack is now [(n-1), 0].
    >           # Peek and compare if (n-1) > 0.
    [           # If the condition is true, execute this block:
      %         # Pop the 0 used for comparison to clean the stack.
      countdown:# Now, recurse. The stack is clean for the next iteration.
    ]
]
countdown:      # Initial call to start the loop.
```

## Ampell Syntax Guide

| Command             | Description                                     |
|---------------------|------------------------------------------------|
| `&[value]`          | Push value (number, text, or variable) onto stack |
| `^"question"~var`   | Ask user a question, save answer in variable `var` |
| `%`                 | Remove (pop) top of the stack                    |
| `$`                 | Print top of the stack                            |
| `>>var`             | Store top of stack value into variable `var`    |
| `+`                 | Add top two stack values, push result            |
| `−`                 | Subtract top from second top, push result        |
| `×`                 | Multiply top two stack values, push result        |
| `÷`                 | Divide second top by top, push result             |
| `=[logic]`          | If second top equals top, execute logic block     |
| `![logic]`          | If second top not equals top, execute logic block |
| `<[logic]`          | If second top less than top, execute logic block  |
| `>[logic]`          | If second top greater than top, execute logic block |
| `@functionName[logic]` | Define function named `functionName`           |
| `functionName:`     | Call function `functionName`                      |
|`\[stackName]        | Go to or create stackName                         |

## Notes
Speed improvement, hello world took:
```
Hello, world!
That took 0.0010 seconds.
```
Case 1 took:
```
Execution took: 0.0120s
```
^^^ This was counting down from 100, without ```^"question"~var&[n]``` and instead just ```&[100]```.


I am able to get that by changing:
```
    def execute(self, code: str):
        """
        Executes Ampell code through the Lexer -> Parser -> Walker pipeline.
        """
        start_time = time.time()
        tokens = self.tokenize(code)
        parser = AmpellParser(tokens)
        ast = parser.parse()
        self.visit(ast)
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"Execution took: {elapsed_time:.4f}s")
```
With time tracking debug.