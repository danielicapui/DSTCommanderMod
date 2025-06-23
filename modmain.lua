-- modmain.lua (versão segura com tratamento de erro e correção de pcall)

print("[DST_DiscordCommandMod] mod carregado")

local GLOBAL = GLOBAL
local pcall = GLOBAL.pcall
local xpcall = GLOBAL.xpcall

-- Prefabs ignorados
local ignorar = {
    grass = true, sapling = true, flower = true, tree = true,
    pinecone = true, twiggytree = true, berrybush = true,
    evergreen = true, evergreen_sparse = true, deciduoustree = true,
    oceantree = true, oceantree_ripples_short = true, oceantree_roots_short = true
}

-- Bosses identificados por vida alta e som de morte
local bosses = {}
for k, v in pairs(GLOBAL.Prefabs) do
    if v and v.deathsound and v.health and v.health.maxhealth and v.health.maxhealth >= 2000 then
        bosses[k] = true
    end
end

-- Protegido AddPlayerPostInit
AddPlayerPostInit(function(inst)
    local ok, err = pcall(function()
        local nome = inst.GetDisplayName and inst:GetDisplayName() or "??"

        inst:ListenForEvent("say", function(_, data)
            if data and data.message then
                local shard = GLOBAL.TheWorld and (GLOBAL.TheWorld.ismastersim and "Master" or "Caves") or "??"
                print(string.format("[DST_CHAT][%s] %s: %s", shard, nome, data.message))
            end
        end)

        inst:ListenForEvent("death", function(_, data)
            local causa = "desconhecida"
            if data then
                if data.afflicter and data.afflicter.GetDisplayName then
                    causa = data.afflicter:GetDisplayName()
                elseif data.afflicter and data.afflicter.prefab then
                    causa = data.afflicter.prefab
                elseif data.cause then
                    causa = data.cause
                end
            end
            print(string.format("[DST_EVENT] %s morreu (causa: %s)", nome, causa))
        end)

        inst:ListenForEvent("ms_respawnedfromghost", function(_, data)
            if data and data.source and data.source.GetDisplayName then
                inst.revivido_por = data.source:GetDisplayName()
            end
        end)

        inst:ListenForEvent("ms_playerspawn", function()
            if inst.revivido_por then
                print(string.format("[DST_EVENT] %s foi revivido por %s", nome, inst.revivido_por))
                inst.revivido_por = nil
            else
                print(string.format("[DST_EVENT] %s renasceu", nome))
            end
        end)

        inst:DoTaskInTime(0, function()
            print(string.format("[DST_EVENT] %s entrou no servidor", nome))
        end)

        inst:ListenForEvent("shardtransition", function(_, data)
            local destino = (data and data.to) or "desconhecido"
            print(string.format("[DST_EVENT] %s mudou para o shard: %s", nome, destino))
        end)

        inst:ListenForEvent("ms_playerleft", function()
            print(string.format("[DST_EVENT] %s saiu do servidor", nome))
        end)
    end)

    if not ok then
        print("[DST_DiscordCommandMod][ERRO] em AddPlayerPostInit: " .. tostring(err))
    end
end)

-- Protegido AddPrefabPostInitAny
AddPrefabPostInitAny(function(inst)
    if not GLOBAL.TheNet:GetIsServer() then return end

    local ok, err = pcall(function()
        inst:ListenForEvent("onignite", function()
            if inst and inst:IsValid() then
                local prefab = inst.prefab or "??"
                if not ignorar[prefab] then
                    local causador = inst.components.burnable and inst.components.burnable:GetLastAttacker()
                    local autor = (causador and causador.GetDisplayName and causador:GetDisplayName()) or "desconhecido"
                    print(string.format("[DST_EVENT] %s colocou fogo em '%s'", autor, prefab))
                end
            end
        end)

        inst:ListenForEvent("onremove", function()
            if inst and inst:IsValid() then
                local prefab = inst.prefab or "??"
                if not ignorar[prefab] then
                    local causador = inst.last_attacker
                    local autor = (causador and causador.GetDisplayName and causador:GetDisplayName()) or "desconhecido"
                    print(string.format("[DST_EVENT] %s destruiu '%s'", autor, prefab))
                end
            end
        end)

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

    if not ok then
        print("[DST_DiscordCommandMod][ERRO] em AddPrefabPostInitAny: " .. tostring(err))
    end
end)

-- Inicialização do shard
AddSimPostInit(function()
    local function init()
        if GLOBAL.TheWorld then
            local shard = GLOBAL.TheWorld.ismastersim and "Master" or "Caves"
            if GLOBAL.TheShard and GLOBAL.TheShard.GetShardId then
                shard = GLOBAL.TheShard:GetShardId() or shard
            end
            print(string.format("[DST_DiscordCommandMod] ativo no shard %s; chat prefixado com [DST_CHAT]", shard))
        else
            GLOBAL.TheWorld:DoTaskInTime(0.25, init)
        end
    end
    init()
end)
