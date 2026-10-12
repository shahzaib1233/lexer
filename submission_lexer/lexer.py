#!/usr/bin/env python3
"""
==============================================================================
 MiniLang - Lexical Analyzer (Lexer)  [Phase 1]
==============================================================================

     Source Code  ──▶  [ LEXER ]  ──▶  Tokens  ──▶  Parser  ──▶  AST

 This lexer reads the source code CHARACTER BY CHARACTER (no regular-expression
 shortcuts), groups the characters into lexemes, classifies each lexeme into a
 token category, and produces a flat stream of Token objects.

 Whitespace and comments are skipped (they are not tokens).
 Lexical errors are collected with line/column info and reported at the end,
 so that one bad character does not hide the rest of the program's errors.

 Usage:
     python3 lexer.py                 # token stream of the built-in sample
     python3 lexer.py sample.mini     # token stream of the given file

 To run the WHOLE compiler (lexer + parser + analyzer + interpreter) use
 minilang.py instead.
==============================================================================
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum
from typing import Any, List


# =============================================================================
# 1. TOKEN TYPES  (the categories the lexer can produce)
# =============================================================================

class TokenType(Enum):
    # ---- Keywords (reserved words, case sensitive) -------------------------
    LET_KEYWORD = "LET_KEYWORD"            # Let
    PRINT_KEYWORD = "PRINT_KEYWORD"        # print
    IF_KEYWORD = "IF_KEYWORD"              # if
    ELSE_KEYWORD = "ELSE_KEYWORD"          # else

    # ---- Names and literals ------------------------------------------------
    IDENTIFIER = "IDENTIFIER"              # name, y, total_marks
    NUMBER_LITERAL = "NUMBER_LITERAL"      # 3, 18, 3.5
    STRING_LITERAL = "STRING_LITERAL"      # "abc", "not adult"

    # ---- Arithmetic operators ---------------------------------------------
    PLUS_OPERATOR = "PLUS_OPERATOR"        # +   (also used for string concatenation)
    MINUS_OPERATOR = "MINUS_OPERATOR"      # -
    STAR_OPERATOR = "STAR_OPERATOR"        # *
    SLASH_OPERATOR = "SLASH_OPERATOR"      # /
    PERCENT_OPERATOR = "PERCENT_OPERATOR"  # %

    # ---- Assignment operator ----------------------------------------------
    ASSIGN_OPERATOR = "ASSIGN_OPERATOR"    # =

    # ---- Relational / comparison operators --------------------------------
    EQUAL_EQUAL = "EQUAL_EQUAL"            # ==
    NOT_EQUAL = "NOT_EQUAL"                # !=
    LESS_THAN = "LESS_THAN"                # <
    GREATER_THAN = "GREATER_THAN"          # >
    LESS_THAN_OR_EQUAL = "LESS_THAN_OR_EQUAL"      # <=
    GREATER_THAN_OR_EQUAL = "GREATER_THAN_OR_EQUAL" # >=

    # ---- Separators / punctuation -----------------------------------------
    LEFT_BRACE = "LEFT_BRACE"              # {
    RIGHT_BRACE = "RIGHT_BRACE"            # }
    LEFT_PAREN = "LEFT_PAREN"              # (
    RIGHT_PAREN = "RIGHT_PAREN"            # )
    SEMICOLON = "SEMICOLON"                # ;
    COMMA = "COMMA"                        # ,

    # ---- End of file -------------------------------------------------------
    EOF = "EOF"                            # virtual token, tells the parser input is over


# Reserved words. A word is looked up here AFTER it has been scanned as an
# identifier; this is the standard "identifier first, then keyword lookup"
# technique and it keeps the scanner simple.
KEYWORDS = {
    "let": TokenType.LET_KEYWORD,      # both spellings are accepted
    "Let": TokenType.LET_KEYWORD,
    "print": TokenType.PRINT_KEYWORD,
    "if": TokenType.IF_KEYWORD,
    "else": TokenType.ELSE_KEYWORD,
}

# Single-character tokens that need no look-ahead.
SINGLE_CHAR_TOKENS = {
    "+": TokenType.PLUS_OPERATOR,
    "-": TokenType.MINUS_OPERATOR,
    "*": TokenType.STAR_OPERATOR,
    "/": TokenType.SLASH_OPERATOR,
    "%": TokenType.PERCENT_OPERATOR,
    "{": TokenType.LEFT_BRACE,
    "}": TokenType.RIGHT_BRACE,
    "(": TokenType.LEFT_PAREN,
    ")": TokenType.RIGHT_PAREN,
    ";": TokenType.SEMICOLON,
    ",": TokenType.COMMA,
}


# =============================================================================
# 2. TOKEN AND ERROR OBJECTS
# =============================================================================

@dataclass
class Token:
    """
    One token produced by the lexer.

    type   : the CATEGORY   (e.g. TokenType.IDENTIFIER)
    lexeme : the actual text taken from the source (e.g. 'name')
    value  : the semantic value of a literal (3 -> int 3, "abc" -> str abc);
             None for tokens that carry no value (operators, separators)
    line   : 1-based line number where the lexeme starts
    column : 1-based column number where the lexeme starts
    """
    type: TokenType
    lexeme: str
    value: Any = None
    line: int = 0
    column: int = 0

    def __str__(self) -> str:
        shown = "" if self.value is None else repr(self.value)
        return f"<{self.type.value} '{self.lexeme}' {shown} @{self.line}:{self.column}>"


@dataclass
class LexicalError:
    """A single lexical error, with the position where it was detected."""
    message: str
    line: int
    column: int

    def __str__(self) -> str:
        return f"Lexical error [line {self.line}, col {self.column}]: {self.message}"


# =============================================================================
# 3. THE LEXER
# =============================================================================

class Lexer:
    """
    Hand-written scanner for MiniLang.

    The scanner keeps a cursor (self.pos) over the source string and walks it
    forward one character at a time. At every step it looks at the current
    character and decides which scanning routine to run:

        letter or '_'  -> identifier / keyword
        digit          -> number literal
        '"'            -> string literal
        anything else  -> operator or separator (with maximal-munch look-ahead)
    """

    def __init__(self, source: str) -> None:
        self.source: str = source
        self.pos: int = 0          # index of the next character to read
        self.line: int = 1         # current line   (1-based)
        self.column: int = 1       # current column (1-based)
        self.tokens: List[Token] = []
        self.errors: List[LexicalError] = []

    # ------------------------------------------------------------------ #
    # 3.1  Low level cursor helpers                                      #
    # ------------------------------------------------------------------ #

    def _is_at_end(self) -> bool:
        return self.pos >= len(self.source)

    def _peek(self) -> str:
        """Current character without consuming it. '\\0' past the end."""
        if self._is_at_end():
            return "\0"
        return self.source[self.pos]

    def _peek_next(self) -> str:
        """The character after the current one, for 2-character operators."""
        if self.pos + 1 >= len(self.source):
            return "\0"
        return self.source[self.pos + 1]

    def _advance(self) -> str:
        """Consume the current character and return it, tracking line/column."""
        ch = self.source[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return ch

    def _match(self, expected: str) -> bool:
        """Consume the current character only if it equals `expected`."""
        if self._is_at_end() or self.source[self.pos] != expected:
            return False
        self._advance()
        return True

    def _add(self, ttype: TokenType, lexeme: str, value: Any,
             line: int, column: int) -> None:
        self.tokens.append(Token(ttype, lexeme, value, line, column))

    def _error(self, message: str, line: int, column: int) -> None:
        self.errors.append(LexicalError(message, line, column))

    @staticmethod
    def _is_alpha(ch: str) -> bool:
        # ASCII only, exactly as the identifier rule [A-Za-z_] states.
        # NOTE: str.isalpha() is deliberately NOT used here, because it also
        # accepts Unicode letters (e.g. 'e', Urdu/Arabic script).
        return ("a" <= ch <= "z") or ("A" <= ch <= "Z") or ch == "_"

    @staticmethod
    def _is_digit(ch: str) -> bool:
        return "0" <= ch <= "9"

    @classmethod
    def _is_alnum(cls, ch: str) -> bool:
        return cls._is_alpha(ch) or cls._is_digit(ch)

    # ------------------------------------------------------------------ #
    # 3.2  Main loop                                                     #
    # ------------------------------------------------------------------ #

    def tokenize(self) -> List[Token]:
        """Scan the whole source and return the token stream."""
        while True:
            self._skip_whitespace_and_comments()
            if self._is_at_end():
                break

            start_line, start_col = self.line, self.column
            ch = self._peek()

            if self._is_alpha(ch):
                self._scan_identifier(start_line, start_col)
            elif self._is_digit(ch):
                self._scan_number(start_line, start_col)
            elif ch == '"':
                self._scan_string(start_line, start_col)
            else:
                self._scan_operator_or_separator(start_line, start_col)

        self._add(TokenType.EOF, "", None, self.line, self.column)
        return self.tokens

    # ------------------------------------------------------------------ #
    # 3.3  Skipping: whitespace, // line comments, /* block comments */   #
    # ------------------------------------------------------------------ #

    def _skip_whitespace_and_comments(self) -> None:
        while not self._is_at_end():
            ch = self._peek()

            if ch in " \t\r\n":
                self._advance()

            elif ch == "/" and self._peek_next() == "/":
                while not self._is_at_end() and self._peek() != "\n":
                    self._advance()

            elif ch == "/" and self._peek_next() == "*":
                start_line, start_col = self.line, self.column
                self._advance()          # '/'
                self._advance()          # '*'
                closed = False
                while not self._is_at_end():
                    if self._peek() == "*" and self._peek_next() == "/":
                        self._advance()  # '*'
                        self._advance()  # '/'
                        closed = True
                        break
                    self._advance()
                if not closed:
                    self._error("Unterminated block comment (missing '*/')",
                                start_line, start_col)
            else:
                return

    # ------------------------------------------------------------------ #
    # 3.4  Identifier / keyword                                          #
    #      rule: [A-Za-z_][A-Za-z0-9_]*                                  #
    # ------------------------------------------------------------------ #

    def _scan_identifier(self, line: int, column: int) -> None:
        start = self.pos
        while not self._is_at_end() and self._is_alnum(self._peek()):
            self._advance()

        lexeme = self.source[start:self.pos]
        ttype = KEYWORDS.get(lexeme, TokenType.IDENTIFIER)
        value = lexeme if ttype is TokenType.IDENTIFIER else None
        self._add(ttype, lexeme, value, line, column)

    # ------------------------------------------------------------------ #
    # 3.5  Number literal                                                #
    #      rule: [0-9]+ ( '.' [0-9]+ )?                                  #
    # ------------------------------------------------------------------ #

    def _scan_number(self, line: int, column: int) -> None:
        start = self.pos
        is_real = False

        while not self._is_at_end() and self._is_digit(self._peek()):
            self._advance()

        # A '.' is part of the number only if a digit follows it.
        if self._peek() == "." and self._is_digit(self._peek_next()):
            is_real = True
            self._advance()                      # consume '.'
            while not self._is_at_end() and self._is_digit(self._peek()):
                self._advance()
        elif self._peek() == ".":
            # e.g. "3." -> malformed. Consume the dot so we do not loop.
            self._advance()
            self._error("Malformed number literal: digit expected after '.'",
                        line, column)
            return

        # e.g. "12abc" -> a number glued to a name is not a valid lexeme.
        if self._is_alpha(self._peek()):
            while not self._is_at_end() and self._is_alnum(self._peek()):
                self._advance()
            bad = self.source[start:self.pos]
            self._error(f"Invalid number literal '{bad}'", line, column)
            return

        lexeme = self.source[start:self.pos]
        value = float(lexeme) if is_real else int(lexeme)
        self._add(TokenType.NUMBER_LITERAL, lexeme, value, line, column)

    # ------------------------------------------------------------------ #
    # 3.6  String literal                                                #
    #      rule: '"' ( any char except '"' and newline | escape )* '"'   #
    #      escapes: \n  \t  \r  \"  \\                                   #
    # ------------------------------------------------------------------ #

    def _scan_string(self, line: int, column: int) -> None:
        ESCAPES = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}

        start = self.pos
        self._advance()                          # consume the opening quote
        chars: List[str] = []

        while True:
            if self._is_at_end() or self._peek() == "\n":
                self._error("Unterminated string literal (missing closing '\"')",
                            line, column)
                return

            ch = self._advance()

            if ch == '"':                        # closing quote -> done
                break

            if ch == "\\":
                if self._is_at_end() or self._peek() == "\n":
                    self._error("Unterminated escape sequence in string",
                                self.line, self.column)
                    return
                esc = self._advance()
                if esc in ESCAPES:
                    chars.append(ESCAPES[esc])
                else:
                    self._error(f"Unknown escape sequence '\\{esc}'",
                                self.line, self.column)
                    chars.append(esc)
            else:
                chars.append(ch)

        lexeme = self.source[start:self.pos]      # includes both quotes
        self._add(TokenType.STRING_LITERAL, lexeme, "".join(chars), line, column)

    # ------------------------------------------------------------------ #
    # 3.7  Operators and separators                                      #
    #      Maximal munch: always try the 2-character operator first,     #
    #      so "==" never becomes "=" "=" and "<=" never becomes "<" "=". #
    # ------------------------------------------------------------------ #

    def _scan_operator_or_separator(self, line: int, column: int) -> None:
        ch = self._advance()

        if ch == "=":
            if self._match("="):
                self._add(TokenType.EQUAL_EQUAL, "==", None, line, column)
            else:
                self._add(TokenType.ASSIGN_OPERATOR, "=", None, line, column)
            return

        if ch == "!":
            if self._match("="):
                self._add(TokenType.NOT_EQUAL, "!=", None, line, column)
            else:
                self._error("Unexpected character '!' (did you mean '!=' ?)",
                            line, column)
            return

        if ch == "<":
            if self._match("="):
                self._add(TokenType.LESS_THAN_OR_EQUAL, "<=", None, line, column)
            else:
                self._add(TokenType.LESS_THAN, "<", None, line, column)
            return

        if ch == ">":
            if self._match("="):
                self._add(TokenType.GREATER_THAN_OR_EQUAL, ">=", None, line, column)
            else:
                self._add(TokenType.GREATER_THAN, ">", None, line, column)
            return

        if ch in SINGLE_CHAR_TOKENS:
            self._add(SINGLE_CHAR_TOKENS[ch], ch, None, line, column)
            return

        self._error(f"Unexpected character {ch!r}", line, column)


# =============================================================================
# 4. PRETTY PRINTING (so the token stream is readable on the terminal)
# =============================================================================

def print_token_table(tokens: List[Token]) -> None:
    header = f"{'#':>3}  {'TOKEN TYPE':<24} {'LEXEME':<16} {'VALUE':<16} {'LINE:COL':>9}"
    print(header)
    print("-" * len(header))
    for i, tok in enumerate(tokens, 1):
        value = "" if tok.value is None else repr(tok.value)
        lexeme = tok.lexeme if tok.type is not TokenType.EOF else "<eof>"
        pos = f"{tok.line}:{tok.column}"
        print(f"{i:>3}  {tok.type.value:<24} {lexeme:<16} {value:<16} {pos:>9}")


def print_errors(errors: List[LexicalError]) -> None:
    print()
    print(f"{len(errors)} lexical error(s) found:")
    for err in errors:
        print("  " + str(err))


# =============================================================================
# 5. BUILT-IN SAMPLE PROGRAM + ENTRY POINT
# =============================================================================

SAMPLE_PROGRAM = '''{
    Let name = "abc";
    Let y = 3;
    print y;
    y = 3 * 2 + 5;
    print name;
    if (y < 18) print "not adult";
}
'''


def main(argv: List[str]) -> int:
    if len(argv) > 1:
        try:
            with open(argv[1], "r", encoding="utf-8") as fh:
                source = fh.read()
        except OSError as exc:
            print(f"Cannot read source file: {exc}", file=sys.stderr)
            return 2
        title = f"Source file: {argv[1]}"
    else:
        source = SAMPLE_PROGRAM
        title = "No input file given - using the built-in sample program"

    print("=" * 72)
    print(" MiniLang Lexical Analyzer")
    print("=" * 72)
    print(title)
    print("-" * 72)
    for n, text in enumerate(source.splitlines(), 1):
        print(f"{n:>3} | {text}")
    print("-" * 72)
    print()

    lexer = Lexer(source)
    tokens = lexer.tokenize()

    print_token_table(tokens)

    print()
    print(f"Total tokens (including EOF): {len(tokens)}")

    if lexer.errors:
        print_errors(lexer.errors)
        return 1

    print("No lexical errors.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
