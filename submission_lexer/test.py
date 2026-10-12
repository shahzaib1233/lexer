from lexer import Lexer

code = 'let x,yz = 10; if(x>1){print("Hello World");} else {print("Goodbye World");}'

lexer = Lexer(code)
tokens = lexer.tokenize()

for tok in tokens:
    print(tok)