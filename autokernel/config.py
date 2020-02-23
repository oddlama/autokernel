import os
import shlex

class Statement:
    pass

class Context:
    subcontexts = {}

class SingletonContext:
    def __init__(self, cfg, ctx, tokens):
        if len(tokens) != 0:
            raise ParsingException("'{}' context does not take parameters".format(self.name))

        # If the parent has an existing subcontext of this type, append to it.
        # Otherwise, set us as the subcontext for this type of the given parent context.
        if self.__class__ not in ctx.subcontexts:
            ctx.subcontexts[self.__class__] = self
        ctx.subcontexts[self.__class__]._parse(cfg, ctx, tokens)

class SetStatement(Statement):
    def __init__(self, cfg, ctx, tokens):
        pass

class AssertStatement(Statement):
    def __init__(self, cfg, ctx, tokens):
        pass

class UseStatement(Statement):
    def __init__(self, cfg, ctx, tokens):
        pass

class SymbolContext(Context):
    keywords = {
        'set': SetStatement,
        'assert': AssertStatement,
        'use': UseStatement,
    }

    def __init__(self, cfg, ctx, tokens):
        raise Exception("SymbolContext must be used as a mixin!")

class ModuleContext(Context, SymbolContext):
    name = 'module'
    def __init__(self, cfg, ctx, tokens):
        if len(tokens) != 1:
            raise ParsingException("module definition requires exactly one identifier")

class BaseStatement(Statement):
    def __init__(self, cfg, ctx, tokens):
        if len(tokens) != 1:
            raise ParsingException("base statement requires exactly one argument")

class ModuleDirStatement(Statement):
    def __init__(self, cfg, ctx, tokens):
        pass

class KernelContext(SingletonContext, SymbolContext):
    name = 'kernel'
    keywords = {
        'base': BaseStatement,
    }

    def _parse(self, cfg, ctx, tokens):
        pass

class GenkernelContext(SingletonContext):
    name = 'genkernel'
    keywords = {
        'add_param': None,
    }

    def _parse(self, cfg, ctx, tokens):
        pass

class InitramfsContext(SingletonContext):
    name = 'initramfs'
    keywords = {
        'add_cmdline': None,
        'static_cmdline': None,
        'genkernel': GenkernelContext,
    }

    def _parse(self, cfg, ctx, tokens):
        pass

class InstallContext(Context):
    name = 'install'
    keywords = {
        'mode': None,
        'target_dir': None,
        'target': None,
        'add_efi_boot_entry': None,
    }

    def _parse(self, cfg, ctx, tokens):
        pass

class RootContext(Context):
    keywords = {
        'module_dir': ModuleDirStatement,
        'module': ModuleContext,
        'kernel': KernelContext,
        'initramfs': InitramfsContext,
        'install': InstallContext,
    }

    def __init__(self):
        pass

class Config:
    """
    The configuration class is used to parse a configuration file
    and provide access to the configuration data
    """

    def __init__(self, filename):
        """
        Loads the given configuration file
        """
        self._load_config(filename)

    def _load_config(self, filename):
        with open(filename, 'r') as f:
            tokens = shlex.split(f.read(), comments=True)

        root_context = RootContext()
        cur_context = root_context
        while len(tokens) > 0:
            keyword = tokens.pop_first()
            if t in keywords:
                if context:
                    find token ending in {
                    args = tokens.pop[:idx]
                else if statement
                    find token ending in ;
                    args = tokens.pop[:idx]
            else:
                if }
                    go up one lvl
                elif ;
                    empty statement
                else
                    unknown keywords
