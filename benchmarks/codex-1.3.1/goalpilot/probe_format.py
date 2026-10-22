"""Bounded pre-freeze repair of an unambiguously invalid number/quote adjacency."""
import io
import tokenize


def normalize(program):
    original=program;repairs=[]
    for _ in range(4):
        try:
            compile(program,'acceptance','exec')
            return program,repairs
        except SyntaxError:pass
        tokens=[]
        try:
            for token in tokenize.generate_tokens(io.StringIO(program).readline):tokens.append(token)
        except (tokenize.TokenError,IndentationError,SyntaxError):pass
        lines=program.splitlines(keepends=True);position=None
        for token in tokens:
            if token.type!=tokenize.NUMBER:continue
            line,column=token.end
            if column+1<len(lines[line-1])and lines[line-1][column]in "\"'"and lines[line-1][column+1]in '),]}:':
                position=sum(map(len,lines[:line-1]))+column
                repairs.append({'line':line,'column':column,'removed_stray_quote':program[position],
                                'reason':'Invalid NUMBER immediately followed by quote and closing punctuation; numeric token unchanged'})
                break
        if position is None:return original,[]
        program=program[:position]+program[position+1:]
    try:compile(program,'acceptance','exec')
    except SyntaxError:return original,[]
    return program,repairs
