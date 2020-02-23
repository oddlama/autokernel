import os
import shlex
import sys
from . import log

class ConfigParsingException(Exception):
    pass

class Statement:
    parser_type = 'statement'

    def __init__(self, arguments):
        """
        Creates a new statement
        """
        # TODO nope
        self.arguments = arguments

class Context:
    """
    A base class for all context classes. Can parse a set of tokens,
    and creates subcontexts and statements depending on the derived classes keywords.
    """
    parser_type = 'context'
    append = False
    mixin_contexts = {}

    def __init__(self, parent, arguments=[]):
        """
        Creates a new context given the parent context
        """
        self.parent = parent
        self.parse_arguments(arguments)
        self.items = []

        # Create mixin context classes with us as parent,
        # if we have mixin_contexts
        for attr in self.mixin_contexts:
            setattr(self, attr, self.mixin_contexts[attr](self))

    def parse_arguments(self, arguments):
        """
        Parses given arguments
        """
        if len(arguments) != 0:
            raise ConfigParsingException("'{}' requires no arguments".format(self.keyword))

    def _get_keyword_parser(self, keyword):
        """
        Returns the correct parser class for the given keyword
        """
        parser = next((i for i in self.keywords if i.keyword == keyword), None)
        if parser:
            # We are the context, because the keyword is in our keyword list
            return (self, parser)

        # Try to find a mixin that accepts the keyword,
        # if we did not recognize the keyword
        if not parser:
            for attr in self.mixin_contexts:
                subctx = getattr(self, attr)
                parser = subctx._get_keyword_parser(keyword)
                if parser:
                    return (subctx, parser)

        # Unknown keyword
        return (None, None)

    def parse(self, root, tokens):
        """
        Parses all given tokens as statements or subcontexts inside this current context.
        """
        while len(tokens) > 0:
            keyword = tokens[0]

            # Our section got closed
            if keyword == "}":
                if self == root:
                    # You cannot close the root section
                    raise ConfigParsingException("Unmatched '}'")
                # Return remaining tokens to the parent context
                return tokens

            # Get parser by keyword
            ctx, parser = self._get_keyword_parser(keyword)
            if not parser:
                raise ConfigParsingException("Unknown keyword '{}' in context '{}'".format(keyword, self.keyword))

            if parser.parser_type == 'context':
                # If the keyword opens a new context, begin with finding
                # the opening brace
                last_token_idx = next((i for i,x in enumerate(tokens) if x.endswith('{')), 0)
                if not last_token_idx:
                    raise ConfigParsingException("Missing opening brace for '{}'".format(parser.keyword))

                if len(tokens[last_token_idx]) == 1:
                    # Remove the whole token if it is only the brace
                    arguments = tokens[:last_token_idx]
                elif len(tokens[last_token_idx]) > 1:
                    # Remove the opening brace from the last token
                    arguments = tokens[:last_token_idx+1]
                    arguments[-1] = arguments[-1][:-1]
                tokens = tokens[last_token_idx+1:]

                # If the new context is a singleton, try to append to an existing context.
                pi = None
                if parser.append:
                    pi = next((i for i in items if i.__class__ == parser), None)

                # Create a new context, if required
                if not pi:
                    pi = parser(self, arguments)
                    self.items.append(pi)

                # Parse the tokens with the given context from now on, and resume
                # with all unmatched tokens later.
                tokens = pi.parse(root, tokens)
            elif parser.parser_type == 'statement':
                # If the keyword begins a statement, begin with finding the terminating semicolon
                last_token_idx = next((i for i,x in enumerate(tokens) if x.endswith(';')), 0)
                if not last_token_idx:
                    raise ConfigParsingException("Missing semicolon for '{}'".format(parser.keyword))

                if len(tokens[last_token_idx]) == 1:
                    # Remove the whole token if it is only the brace
                    arguments = tokens[:last_token_idx]
                elif len(tokens[last_token_idx]) > 1:
                    # Remove the opening brace from the last token
                    arguments = tokens[:last_token_idx+1]
                    arguments[-1] = arguments[-1][:-1]
                tokens = tokens[last_token_idx+1:]

                # Parse the tokens with the given context from now on, and resume
                # with all unmatched tokens later.
                self.items.append(parser(arguments))
            else:
                raise Exception("Invalid parser type for class {}".format(parser.__class__.__name__))

class SetStatement(Statement):
    keyword = "set"

    def parse_arguments(self, arguments):
        pass

class AssertStatement(Statement):
    keyword = "assert"

    def parse_arguments(self, arguments):
        pass

class UseStatement(Statement):
    keyword = "use"

    def parse_arguments(self, arguments):
        pass

class SymbolContext(Context):
    keyword = 'symbol'
    keywords = [
        SetStatement,
        AssertStatement,
        UseStatement,
    ]

class ModuleContext(Context):
    keyword = 'module'
    keywords = []
    mixin_contexts = {
        'symbols': SymbolContext
    }

    def parse_arguments(self, arguments):
        if len(arguments) != 1:
            raise ConfigParsingException("module definition requires exactly one identifier")

class BaseStatement(Statement):
    keyword = 'base'
    def parse_arguments(self, arguments):
        if len(arguments) != 1:
            raise ConfigParsingException("base statement requires exactly one argument")

class ModuleDirStatement(Statement):
    keyword = 'module'
    def parse_arguments(self, arguments):
        if len(arguments) != 1:
            raise ConfigParsingException("module_dir statement requires exactly one argument")

class KernelContext(Context):
    keyword = 'kernel'
    append = True
    keywords = [
        BaseStatement,
    ]

    mixin_contexts = {
        'symbols': SymbolContext
    }

class GenkernelContext(Context):
    keyword = 'genkernel'
    append = True
    keywords = [
        #'add_param'
    ]

class InitramfsContext(Context):
    keyword = 'initramfs'
    append = True
    keywords = [
        #'add_cmdline': None,
        #'static_cmdline': None,
        GenkernelContext,
    ]

class InstallContext(Context):
    keyword = 'install'
    keywords = [
        #'mode': None,
        #'target_dir': None,
        #'target': None,
        #'add_efi_boot_entry': None,
    ]

class RootContext(Context):
    keyword = 'root'
    keywords = [
        ModuleDirStatement,
        ModuleContext,
        KernelContext,
        InitramfsContext,
        InstallContext,
    ]

class Config(RootContext):
    """
    The configuration class is used to parse a configuration file
    and provide access to the configuration data
    """

    def __init__(self, filename):
        """
        Loads the given configuration file
        """
        super().__init__(None)
        self._load_config(filename)

    def _load_config(self, filename):
        with open(filename, 'r') as f:
            tokens = shlex.split(f.read(), comments=True)

        try:
            # Parse all tokens inside the root context
            self.parse(self, tokens)
        except ConfigParsingException as e:
            log.error(str(e))
            sys.exit(1)
