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

function Symbol:__name() return self.name end
function Symbol:__tostring()
	return "Symbol{name=" .. self.name .. ", value=" .. self:value() .. "}"
end

function Symbol:type() return ak.symbol_get_type(self.name) end
function Symbol:str_value() return ak.symbol_get_string(self.name) end

function Symbol:is(value)
	local stype = self:type()
	if getmetatable(value) == Tristate and (stype == "Boolean" or stype == "Tristate") then
		return value == self:value()
	elseif type(value) == "string" and stype == "String" then
		return value == self:value()
	elseif type(value) == "number" and (stype == "Int" or stype == "Hex") then
		return value == self:value()
	else
		error ("Cannot compare symbol of type " .. stype .. " to value of type " .. type(value))
	end
end

function Symbol:v(value) return self:value() end
function Symbol:value()
	local stype = self:type()
	local str_value = self:str_value()

	if stype == "Boolean" or stype == "Tristate" then
		return tristate_from_str(str_value)
	elseif stype == "Int" or stype == "Hex" then
		return tonumber(str_value)
	elseif stype == "String" then
		return str_value
	else
		error ("Unsupported value type '" .. stype .. "'")
	end
end

function Symbol:__call(value) self:set(value) end
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
