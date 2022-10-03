--###############################################################
-- Tristate

Tristate = { }

function Tristate:new(value)
	o = {}
	setmetatable(o, self)
	self.__index = self
	o.value = value
	return o
end

y = Tristate:new("y")
m = Tristate:new("m")
n = Tristate:new("n")
yes = y
mod = m
no = n

--###############################################################
-- Symbol

Symbol = { }

function Symbol:new(o, name)
	o = o or {}
	setmetatable(o, self)
	self.__index = self
	self.__call = Symbol.call
	o.name = name
	return o
end

function Symbol:call(value)
	self:set(value)
end

function Symbol:set(value)
	if getmetatable(value) == Tristate then
		print("set tristate", self.name, value.value)
		autokernel_symbol_set_tristate(self.name, value.value)
	elseif type(value) == "string" then
		print("set string", self.name, value)
		autokernel_symbol_set_auto(self.name, value)
	elseif type(value) == "number" then
		print("set number", self.name, value)
		autokernel_symbol_set_number(self.name, value)
	elseif type(value) == "boolean" then
		print("set bool", self.name, value)
		autokernel_symbol_set_bool(self.name, value)
	else
		error ("Unsupported value type '" .. type(value) .. "'")
	end
end
