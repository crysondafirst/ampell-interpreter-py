# Ampell Interpreter

Ampell is a simple stack-based programming language with an easy-to-use interpreter.

## Features

- Stack operations: push, pop, peek  
- Variables: store and retrieve values  
- Arithmetic operations: add, subtract, multiply, divide  
- Conditional execution  
- Function definition and calling  
- User input and output  

---

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
| `@functionName[logic]` | Define function named `functionName`            |
| `functionName:`     | Call function `functionName`                       |

