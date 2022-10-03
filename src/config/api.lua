--###############################################################
-- Tristate

Tristate = { }
Tristate.__index = Tristate

function Tristate:new(value)
	o = {}
	setmetatable(o, self)
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
Symbol.__index = Symbol

function Symbol:new(o, name)
	o = o or {}
	setmetatable(o, self)
	o.name = name
	return o
end

function Symbol:__call(value)
	self:set(value)
end

function Symbol:__tostring()
	return "Symbol{name=" .. self.name .. ", value=" .. self:value() .. "}"
end

function Symbol:value()
	return autokernel_symbol_get_string(self.name)
end

function Symbol:set(value)
	if getmetatable(value) == Tristate then
		autokernel_symbol_set_tristate(self.name, value.value)
	elseif type(value) == "string" then
		autokernel_symbol_set_auto(self.name, value)
	elseif type(value) == "number" then
		autokernel_symbol_set_number(self.name, value)
	elseif type(value) == "boolean" then
		autokernel_symbol_set_bool(self.name, value)
	else
		error ("Unsupported value type '" .. type(value) .. "'")
	end
end
