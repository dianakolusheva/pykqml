import io
import logging
from .kqml_exceptions import *

from . import kqml_list
from . import kqml_performative
from .kqml_token import KQMLToken
from .kqml_string import KQMLString
from .kqml_quotation import KQMLQuotation

logger = logging.getLogger('KQMLReader')

class KQMLReader(object):
    def __init__(self, reader):
        self.reader = reader
        self.inbuf = ''

    def close(self):
        self.reader.close()

    def read_char(self):
        ch = self.reader.read(1)
        ch_int = ch[0]
        if ch_int >= 192 and ch_int < 224:
            ch += self.reader.read(1)
        elif ch_int >= 224 and ch_int < 240:
            ch += self.reader.read(2)
        elif ch_int >= 240:
            ch += self.reader.read(3)
        self.inbuf += ch.decode()
        return ch.decode()

    def unget_char(self, ch):
        nbytes = len(ch.encode())
        # Rewind by 1 relative to current position
        self.reader.seek(-nbytes, 1)
        self.reader.write(ch.encode())
        # Rewind by 1 relative to current position
        self.reader.seek(-nbytes, 1)
        self.inbuf = self.inbuf[:-nbytes]

    def peek_char(self):
        if isinstance(self.reader, io.BufferedReader):
            ch_ = self.reader.peek(1)
            if not ch_:
                raise EOFError
            ch = bytes([ch_[0]]).decode()
        else:
            ch = self.read_char()
            self.unget_char(ch)
        return ch

    @staticmethod
    def is_special(ch):
        special_chars = '<>=+-*/&^~_@$%:.!?|'
        if special_chars.find(ch) != -1:
            return True
        else:
            return False

    @staticmethod
    def is_token_char(ch):
        non_token_chars = "'`\"#()"
        if (not ch.isspace()) and  (non_token_chars.find(ch) == -1):
            return True
        else:
            return False

    def read_expr(self, backquoted=False):
        ch = self.peek_char()
        if ch == "'" or ch == "`":
            return self.read_quotation(backquoted)
        elif ch == '"' or ch == "#":
            return self.read_string()
        elif ch == '(':
            return self.read_list(backquoted)
        elif ch == ',':
            if not backquoted:
                ch = self.read_char()
                raise KQMLBadCommandException(self.inbuf)
            else:
                self.read_quotation(backquoted)
        else:
            if self.is_token_char(ch):
                return self.read_token()
            else:
                ch = self.read_char()
                raise KQMLBadCharacterException(self.inbuf)

    def read_token(self):
        buf = ''
        done = False
        can_peek = isinstance(self.reader, io.BufferedReader)
        while not done:
            ch = self.peek_char()
            if self.is_token_char(ch):
                buf += ch
                self.read_char()
            else:
                done = True
        return KQMLToken(buf)

    def read_quotation(self, backquoted):
        ch = self.read_char()
        if ch == '`':
            return KQMLQuotation(ch, self.read_expr(True))
        elif ch == "'" or ch == ',':
            return KQMLQuotation(ch, self.read_expr(backquoted))
        else:
            return None

    def read_string(self):
        ch = self.read_char()
        if ch == '"':
            return self.read_quoted_string()
        else:
            return self.read_hashed_string()

    def read_quoted_string(self):
        buf = ''
        while True:
            ch = self.read_char()
            if ch == '"':
                break
            if ch == '\\':
                # Look at the next character
                ch = self.read_char()
                # If it is another backslash, preserve the two
                if ch == '\\':
                    buf += '\\\\'
                    continue
                # Otherwise only the next character is added to the buffer
            buf += ch
        return KQMLString(buf)

    def read_hashed_string(self):
        buf = ''
        count = 0
        while True:
            ch = self.read_char()
            if ch == '"':
                break
            if not ch.isdigit():
                raise KQMLBadHashException(self.inbuf)
            else:
                count = count * 10 + int(ch)
        if count == 0:
            return KQMLString('')
        else:
            for _ in range(count):
                buf += self.read_char()
        return KQMLString(buf)

    def read_list_for_file(self):
        self.skip_whitespace()
        return self.read_list()
        # TODO: handle EOF

    def read_list(self, backquoted=False):
        lst = kqml_list.KQMLList()
        ch = self.read_char()
        if ch != '(':
            raise KQMLBadOpenException(self.inbuf)
        self.skip_whitespace()
        while True:
            ch = self.peek_char()
            if ch == ')':
                break
            lst.append(self.read_expr(backquoted))
            ch = self.peek_char()
            if ch != ')':
                if ch != '(':
                    self.read_whitespace()
        ch = self.read_char()
        if ch != ')':
            raise KQMLBadCloseException(self.inbuf)
        return lst

    def read_whitespace(self):
        ch = self.read_char()
        if not ch.isspace():
            logger.error('Expected whitespace, got: %s' % ch)
            raise KQMLExpectedWhitespaceException(self.inbuf)
        else:
            self.skip_whitespace()

    def skip_whitespace(self):
        done = False
        while not done:
            ch = self.peek_char()
            if not ch.isspace():
                done = True
            else:
                self.read_char()

    def read_performative(self):
        self.inbuf = ''
        self.skip_whitespace()
        self.inbuf = ''
        expr = self.read_expr()
        if isinstance(expr, kqml_list.KQMLList):
            return kqml_performative.KQMLPerformative(expr)
        else:
            raise KQMLExpectedListException(self.inbuf)
