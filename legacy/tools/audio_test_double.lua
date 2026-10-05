-- Presentation seam for subsystem tests. test_damsel_audio exercises the real
-- dispatcher, realm isolation, lifecycle suppression and recipient throttles.
return {
    Muted=function() return false end,
    Path=function(_,id) return 'legend_of_deborah/feedback/'..id..'.wav' end,
    Play=function(_,id)
        local path='legend_of_deborah/feedback/'..id..'.wav'
        if surface and surface.PlaySound then surface.PlaySound(path)
        elseif LocalPlayer then LocalPlayer():EmitSound(path,0,100,.65,0) end
        return true
    end,
    Emit=function() return true end,ToPlayer=function() return true end,At=function() end
}
