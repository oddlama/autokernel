Symbol = { }

function dump(o)
	if type(o) == 'table' then
		local s = '{ '
		for k,v in pairs(o) do
			if type(k) ~= 'number' then k = '"'..k..'"' end
			s = s .. '['..k..'] = ' .. dump(v) .. ','
		end
		return s .. '} '
	else
		return tostring(o)
	end
end

function Symbol:new(o, name)
	o = o or {}
	setmetatable(o, self)
	self.__index = self
	self.__call = Symbol.call
	o.name = name
	return o
end

function Symbol:call(value)
	self.set(value)
end

function Symbol:call(value)
	print("set v ", type(value), self.name, value)
	print(dump(value))
	if type(value) == "string" then
		print("set string", self.name, value)
	end
end

EXPERT = Symbol:new(nil, "EXPERT")
TEST = Symbol:new(nil, "TEST")
