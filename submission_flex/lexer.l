/*
 * ===========================================================================
 *  MiniLang - Lexical Analyzer (Flex / win_flex version)
 * ===========================================================================
 *
 *  This is the Flex equivalent of lexer.py.  It uses pattern rules instead of
 *  hand-written character-by-character scanning.  Flex reads these rules and
 *  AUTO-GENERATES the C lexer code.
 *
 *  HOW TO BUILD AND RUN (Windows, with win_flex + GCC):
 *  ---------------------------------------------------
 *  1.  win_flex  lexer.l                      --> generates  lex.yy.c
 *  2.  gcc  lex.yy.c  -o lexer.exe            --> compiles the lexer
 *  3.  lexer.exe  input.txt                   --> tokenises the file
 *      (or just:  lexer.exe                   --> reads from stdin)
 *
 *  Token output matches the Python lexer's table format so you can compare
 *  both side-by-side.
 * ===========================================================================
 */

%{
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ---- state ---- */
static int  column       = 1;
static int  token_count  = 0;
static int  error_count  = 0;
static int  tok_col;                /* start-column of current match */

/* string literal buffers */
static char strbuf[4096];
static int  strpos;
static int  str_start_line;
static int  str_start_col;
static char rawbuf[4096];           /* string exactly as written in source */
static int  rawpos;

/* block-comment origin (for unterminated-comment error) */
static int  comment_start_line;
static int  comment_start_col;

/*
 * YY_USER_ACTION runs before EVERY rule action.
 * It saves the start column, then advances column by the match length,
 * resetting on newlines so line:col stays correct.
 */
#define YY_USER_ACTION {                                \
    tok_col = column;                                   \
    for (int _i = 0; _i < yyleng; _i++) {               \
        if (yytext[_i] == '\n') column = 1;             \
        else                    column++;               \
    }                                                   \
}

/* ---- helpers ---- */
static void emit(const char *type, const char *lexeme, const char *value) {
    token_count++;
    printf("%3d  %-24s %-16s %-16s %5d:%d\n",
           token_count, type, lexeme,
           value ? value : "",
           yylineno, tok_col);
}

static void lex_error(int line, int col, const char *msg) {
    error_count++;
    printf("  Lexical error [line %d, col %d]: %s\n", line, col, msg);
}

/* append the current match to rawbuf (keeps escapes like \n as typed) */
static void raw_append(const char *s) {
    while (*s && rawpos < 4094) rawbuf[rawpos++] = *s++;
}

%}

 /* ---- Flex options ---- */
%option noyywrap
%option yylineno
%option nounistd
%option never-interactive

 /* ---- Exclusive start conditions ---- */
%x STR
%x BLOCK_COMMENT

 /* ---- Named patterns (definitions) ---- */
DIGIT   [0-9]
LETTER  [A-Za-z_]
ALNUM   [A-Za-z0-9_]

%%

 /* ================================================================ */
 /*  WHITESPACE  —  skip spaces, tabs, carriage returns, newlines    */
 /* ================================================================ */

[ \t\r]+        { /* skip */ }
\n              { /* skip (yylineno increments automatically) */ }

 /* ================================================================ */
 /*  LINE COMMENT  //  —  skip everything until end of line          */
 /* ================================================================ */

"//"[^\n]*      { /* skip line comment */ }

 /* ================================================================ */
 /*  BLOCK COMMENT  (slash-star ... star-slash)  —  multi-line       */
 /* ================================================================ */

"/*"  {
    comment_start_line = yylineno;
    comment_start_col  = tok_col;
    BEGIN(BLOCK_COMMENT);
}

<BLOCK_COMMENT>"*/"    { BEGIN(INITIAL); }
<BLOCK_COMMENT>.       { /* skip content */ }
<BLOCK_COMMENT>\n      { /* skip newline inside comment */ }
<BLOCK_COMMENT><<EOF>> {
    lex_error(comment_start_line, comment_start_col,
              "Unterminated block comment (missing '*/')");
    BEGIN(INITIAL);
}

 /* ================================================================ */
 /*  KEYWORDS  —  must appear BEFORE the identifier rule so that     */
 /*  when both match the same length, the earlier (keyword) wins.    */
 /* ================================================================ */

"Let"|"let"     { emit("LET_KEYWORD",   yytext, NULL); }
"print"         { emit("PRINT_KEYWORD", yytext, NULL); }
"if"            { emit("IF_KEYWORD",    yytext, NULL); }
"else"          { emit("ELSE_KEYWORD",  yytext, NULL); }

 /* ================================================================ */
 /*  IDENTIFIERS  —  [A-Za-z_][A-Za-z0-9_]*                         */
 /* ================================================================ */

{LETTER}{ALNUM}*  { emit("IDENTIFIER", yytext, yytext); }

 /* ================================================================ */
 /*  NUMBER LITERALS  —  integers and floats                         */
 /*  Order matters:  float rule first (longer match), then errors,   */
 /*  then plain integer.                                             */
 /* ================================================================ */

{DIGIT}+"."{DIGIT}+  { emit("NUMBER_LITERAL", yytext, yytext); }

{DIGIT}+"."  {
    lex_error(yylineno, tok_col,
              "Malformed number literal: digit expected after '.'");
}

{DIGIT}+{LETTER}{ALNUM}*  {
    char msg[256];
    snprintf(msg, sizeof(msg), "Invalid number literal '%s'", yytext);
    lex_error(yylineno, tok_col, msg);
}

{DIGIT}+  { emit("NUMBER_LITERAL", yytext, yytext); }

 /* ================================================================ */
 /*  STRING LITERALS  —  "..." with escape sequences                 */
 /*  Uses an exclusive start condition (STR) so Flex reads the       */
 /*  string character by character, just like the Python lexer.      */
 /* ================================================================ */

\"  {
    str_start_line = yylineno;
    str_start_col  = tok_col;
    strpos         = 0;
    rawpos         = 0;
    BEGIN(STR);
}

<STR>\\n   { raw_append(yytext); if (strpos < 4094) strbuf[strpos++] = '\n'; }
<STR>\\t   { raw_append(yytext); if (strpos < 4094) strbuf[strpos++] = '\t'; }
<STR>\\r   { raw_append(yytext); if (strpos < 4094) strbuf[strpos++] = '\r'; }
<STR>\\\"  { raw_append(yytext); if (strpos < 4094) strbuf[strpos++] = '"';  }
<STR>\\\\  { raw_append(yytext); if (strpos < 4094) strbuf[strpos++] = '\\'; }

<STR>\\.  {
    char msg[64];
    snprintf(msg, sizeof(msg), "Unknown escape sequence '\\%c'", yytext[1]);
    lex_error(yylineno, tok_col, msg);
    raw_append(yytext);
    if (strpos < 4094) strbuf[strpos++] = yytext[1];
}

<STR>\"  {
    strbuf[strpos] = '\0';
    rawbuf[rawpos] = '\0';
    /* Show the string as written (escapes stay as \n, \t) so real
       newlines/tabs don't break the table; column = opening quote.  */
    char lexeme[4098];
    snprintf(lexeme, sizeof(lexeme), "\"%s\"", rawbuf);
    tok_col = str_start_col;
    emit("STRING_LITERAL", lexeme, rawbuf);
    BEGIN(INITIAL);
}

<STR>\n  {
    lex_error(str_start_line, str_start_col,
              "Unterminated string literal (missing closing '\"')");
    BEGIN(INITIAL);
}

<STR><<EOF>>  {
    lex_error(str_start_line, str_start_col,
              "Unterminated string literal (missing closing '\"')");
    BEGIN(INITIAL);
}

<STR>.  {
    raw_append(yytext);
    if (strpos < 4094) strbuf[strpos++] = yytext[0];
}

 /* ================================================================ */
 /*  TWO-CHARACTER OPERATORS  —  maximal munch ensures "==" is not   */
 /*  split into "=" "=", and "<=" is not split into "<" "=".         */
 /* ================================================================ */

"=="    { emit("EQUAL_EQUAL",             "==", NULL); }
"!="    { emit("NOT_EQUAL",              "!=", NULL); }
"<="    { emit("LESS_THAN_OR_EQUAL",     "<=", NULL); }
">="    { emit("GREATER_THAN_OR_EQUAL",  ">=", NULL); }

 /* ================================================================ */
 /*  SINGLE-CHARACTER OPERATORS                                      */
 /* ================================================================ */

"="     { emit("ASSIGN_OPERATOR",  "=", NULL); }
"+"     { emit("PLUS_OPERATOR",    "+", NULL); }
"-"     { emit("MINUS_OPERATOR",   "-", NULL); }
"*"     { emit("STAR_OPERATOR",    "*", NULL); }
"/"     { emit("SLASH_OPERATOR",   "/", NULL); }
"%"     { emit("PERCENT_OPERATOR", "%", NULL); }
"<"     { emit("LESS_THAN",        "<", NULL); }
">"     { emit("GREATER_THAN",     ">", NULL); }

 /* ================================================================ */
 /*  SEPARATORS / PUNCTUATION                                        */
 /* ================================================================ */

"{"     { emit("LEFT_BRACE",  "{", NULL); }
"}"     { emit("RIGHT_BRACE", "}", NULL); }
"("     { emit("LEFT_PAREN",  "(", NULL); }
")"     { emit("RIGHT_PAREN", ")", NULL); }
";"     { emit("SEMICOLON",   ";", NULL); }
","     { emit("COMMA",       ",", NULL); }

 /* ================================================================ */
 /*  ERROR CASES                                                     */
 /* ================================================================ */

"!"  {
    lex_error(yylineno, tok_col,
              "Unexpected character '!' (did you mean '!=' ?)");
}

.  {
    char msg[64];
    snprintf(msg, sizeof(msg), "Unexpected character '%s'", yytext);
    lex_error(yylineno, tok_col, msg);
}

%%

/* ================================================================== */
/*  MAIN  —  mirrors the Python lexer's output format                 */
/* ================================================================== */

int main(int argc, char *argv[]) {
    printf("========================================================================\n");
    printf(" MiniLang Lexical Analyzer  (Flex / win_flex version)\n");
    printf("========================================================================\n");

    if (argc > 1) {
        FILE *f = fopen(argv[1], "r");
        if (!f) {
            fprintf(stderr, "Cannot open file: %s\n", argv[1]);
            return 2;
        }
        printf("Source file: %s\n", argv[1]);
        yyin = f;
    } else {
        printf("Reading from standard input (type code, then Ctrl+Z Enter to end):\n");
    }

    printf("------------------------------------------------------------------------\n\n");
    printf("%3s  %-24s %-16s %-16s %s\n",
           "#", "TOKEN TYPE", "LEXEME", "VALUE", "LINE:COL");
    printf("------------------------------------------------------------------------\n");

    yylex();

    /* Emit the EOF token, just like the Python lexer */
    token_count++;
    printf("%3d  %-24s %-16s %-16s %5d:%d\n",
           token_count, "EOF", "<eof>", "", yylineno, column);

    printf("\nTotal tokens (including EOF): %d\n", token_count);

    if (error_count > 0) {
        printf("\n%d lexical error(s) found.\n", error_count);
        return 1;
    }

    printf("No lexical errors.\n");

    if (argc > 1) fclose(yyin);
    return 0;
}
