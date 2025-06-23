print("[DST_DiscordCommandMod] mod carregado")

local GLOBAL = GLOBAL

-- Prefabs que serão ignorados ao detectar destruição ou incêndio
local ignorar = {
    grass = true, sapling = true, flower = true, tree = true,
    pinecone = true, twiggytree = true, berrybush = true,
    evergreen = true, evergreen_sparse = true, deciduoustree = true
}

-- Prefabs de bosses para detectar quando forem derrotados
local bosses = {
    deerclops = true, bearger = true, dragonfly = true, moose = true,
    beequeen = true, klaus = true, antlion = true, toadstool = true,
    toadstool_dark = true, fuelweaver = true, crabking = true,
    malbatross = true, twinsboss = true, alteredbeast = true,
    celestialchampion = true
}

AddPlayerPostInit(function(inst)

    -- Chat dos jogadores
    inst:ListenForEvent("say", function(_, data)
        if data.message then
            local nome = inst:GetDisplayName() or "??"
            local shard = "Unknown"
            if GLOBAL.TheShard then
                shard = GLOBAL.TheShard:GetShardId() or (GLOBAL.TheWorld.ismastersim and "Master") or "Caves"
            elseif GLOBAL.TheWorld then
                shard = GLOBAL.TheWorld.ismastersim and "Master" or "Caves"
            end
            print(string.format("[DST_CHAT][%s] %s: %s", shard, nome, data.message))
        end
    end)

    -- Morte do jogador (com causa)
    inst:ListenForEvent("death", function(inst, data)
        local nome = inst:GetDisplayName() or "??"
        local causa = "desconhecida"
        if data and data.afflicter then
            if data.afflicter.GetDisplayName then
                causa = data.afflicter:GetDisplayName()
            elseif data.afflicter.prefab then
                causa = data.afflicter.prefab
            else
                causa = tostring(data.afflicter)
            end
        elseif data and data.cause then
            causa = data.cause
        end
        print(string.format("[DST_EVENT] %s morreu (causa: %s)", nome, causa))
    end)

    -- Registro de quem reviveu o jogador (se aplicável)
    inst:ListenForEvent("ms_respawnedfromghost", function(inst, data)
        if data and data.source and data.source.GetDisplayName then
            inst.revivido_por = data.source:GetDisplayName()
        end
    end)

    -- Respawn (natural ou revivido)
    inst:ListenForEvent("ms_playerspawn", function(inst, data)
        local nome = inst:GetDisplayName() or "??"
        if inst.revivido_por then
            print(string.format("[DST_EVENT] %s foi revivido por %s", nome, inst.revivido_por))
            inst.revivido_por = nil
        else
            print(string.format("[DST_EVENT] %s renasceu", nome))
        end
    end)

    -- Entrada no servidor
    inst:DoTaskInTime(0, function()
        local nome = inst:GetDisplayName() or "??"
        print(string.format("[DST_EVENT] %s entrou no servidor", nome))
    end)

    -- Mudança de shard (ex: para as Cavernas)
    inst:ListenForEvent("shardtransition", function(inst, data)
        local nome = inst:GetDisplayName() or "??"
        local destino = (data and data.to) or "desconhecido"
        print(string.format("[DST_EVENT] %s mudou para o shard: %s", nome, destino))
    end)

    -- Saída do servidor (quando disponível)
    inst:ListenForEvent("ms_playerleft", function(inst)
        local nome = inst:GetDisplayName() or "??"
        print(string.format("[DST_EVENT] %s saiu do servidor", nome))
    end)
end)

-- Eventos gerais para qualquer entidade no mundo (estrutura, boss, etc)
AddPrefabPostInitAny(function(inst)
    if not GLOBAL.TheNet:GetIsServer() then return end

    -- Estrutura pega fogo
    inst:ListenForEvent("onignite", function()
        if inst and inst:IsValid() then
            local prefab = inst.prefab or "??"
            if not ignorar[prefab] then
                local causador = inst.components.burnable and inst.components.burnable:GetLastAttacker()
                local autor = causador and causador.GetDisplayName and causador:GetDisplayName() or "desconhecido"
                print(string.format("[DST_EVENT] %s colocou fogo em '%s'", autor, prefab))
            end
        end
    end)

    -- Estrutura é destruída
    inst:ListenForEvent("onremove", function()
        if inst and inst:IsValid() then
            local prefab = inst.prefab or "??"
            if not ignorar[prefab] then
                local causador = inst.last_attacker or inst:GetCombatTarget()
                local autor = causador and causador.GetDisplayName and causador:GetDisplayName() or "desconhecido"
                print(string.format("[DST_EVENT] %s destruiu '%s'", autor, prefab))
            end
        end
    end)

    -- Boss derrotado
    inst:ListenForEvent("death", function()
        if inst and inst.prefab and bosses[inst.prefab] then
            local killer = "desconhecido"
            if inst.components and inst.components.combat then
                local atk = inst.components.combat.lastattacker
                if atk and atk.GetDisplayName then
                    killer = atk:GetDisplayName()
                end
            end
            print(string.format("[DST_EVENT] %s derrotou o boss '%s'", killer, inst.prefab))
        end
    end)
end)

-- Confirma carregamento do mod no shard correto
AddSimPostInit(function()
    local function init()
        if GLOBAL.TheWorld then
            local shard = "Unknown"
            if GLOBAL.TheShard then
                shard = GLOBAL.TheShard:GetShardId() or (GLOBAL.TheWorld.ismastersim and "Master" or "Caves")
            else
                shard = GLOBAL.TheWorld.ismastersim and "Master" or "Caves"
            end
            print(string.format("[DST_DiscordCommandMod] ativo no shard %s; chat prefixado com [DST_CHAT]", shard))
        else
            GLOBAL.TheWorld:DoTaskInTime(0.25, init)
        end
    end
    init()
end)
