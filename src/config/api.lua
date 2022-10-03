--###############################################################
-- Tristate

Tristate = { }
Tristate.__index = Tristate

function Tristate:new(name, value)
	o = {}
	setmetatable(o, self)
	o.name = name
	o.value = value
	return o
end

function Tristate:__tostring()
	return "Tristate(" .. self.name .. ")"
end

function Tristate.__eq(a, b) return a.value == b.value end
function Tristate.__lt(a, b) return a.value < b.value end
function Tristate.__le(a, b) return a.value <= b.value end

n = Tristate:new("n", 0)
m = Tristate:new("m", 1)
y = Tristate:new("y", 2)
no = n
mod = m
yes = y

function tristate_from_str(str)
	if str == "y" then
		return y
	elseif str == "m" then
		return m
	elseif str == "n" then
		return n
	end
end

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
	if value == nil then
		return self:value()
	else
		self:set(value)
	end
end

function Symbol:__tostring()
	return "Symbol{name=" .. self.name .. ", value=" .. self:value() .. "}"
end

function Symbol:__name() return self.name end
function Symbol:type() return ak.symbol_get_type(self.name) end
function Symbol:str_value() return ak.symbol_get_string(self.name) end

function Symbol:value()
	local type = self:type()
	local str_value = self:str_value()

	if type == "Boolean" or type == "Tristate" then
		return tristate_from_str(str_value)
	elseif type == "Int" or type == "Hex" then
		return tonumber(str_value)
	elseif type == "String" then
		return str_value
	else
		error ("Unsupported value type '" .. type .. "'")
	end
end

function Symbol:set(value)
	if getmetatable(value) == Tristate then
		ak.symbol_set_tristate(self.name, value.name)
	elseif type(value) == "string" then
		ak.symbol_set_auto(self.name, value)
	elseif type(value) == "number" then
		ak.symbol_set_number(self.name, value)
	else
		error ("Unsupported value type '" .. type(value) .. "'")
	end
end
