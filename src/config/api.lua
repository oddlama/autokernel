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
	if type(value) == "string" then
		print("set string", self.name, value)
	else
		print("set v ", type(value), self.name, value)
	end
end
