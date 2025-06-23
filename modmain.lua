print("[DST_DiscordCommandMod] mod carregado")

local GLOBAL = GLOBAL

-- Prefabs ignorados (não usados agora porque removemos destruição e queima)
-- local ignorar = {
--     grass = true, sapling = true, flower = true, tree = true,
--     pinecone = true, twiggytree = true, berrybush = true,
--     evergreen = true, evergreen_sparse = true, deciduoustree = true
-- }

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
        -- Pega userid do jogador para usar no log (nome real do player)
        local nome_jogador = "??"
        if inst.userid then
            nome_jogador = inst.userid
        elseif inst.player_classified and inst.player_classified.userid then
            nome_jogador = inst.player_classified.userid:value() or "??"
        else
            nome_jogador = inst.GetDisplayName and inst:GetDisplayName() or "??"
        end

        -- Pega nome do personagem para ignorar a Charlie
        local nome_char = inst:GetDisplayName() or "??"

        inst:ListenForEvent("say", function(_, data)
            if data and data.message then
                if nome_char ~= "Charlie" then
                    local shard = GLOBAL.TheWorld and (GLOBAL.TheWorld.ismastersim and "Master" or "Caves") or "??"
                    print(string.format("[DST_CHAT][%s] %s: %s", shard, nome_jogador, data.message))
                end
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
            print(string.format("[DST_EVENT] %s morreu (causa: %s)", nome_jogador, causa))
        end)

        inst:ListenForEvent("ms_respawnedfromghost", function(_, data)
            if data and data.source and data.source.GetDisplayName then
                inst.revivido_por = data.source:GetDisplayName()
            end
        end)

        inst:ListenForEvent("ms_playerspawn", function()
            if inst.revivido_por then
                print(string.format("[DST_EVENT] %s foi revivido por %s", nome_jogador, inst.revivido_por))
                inst.revivido_por = nil
            else
                print(string.format("[DST_EVENT] %s renasceu", nome_jogador))
            end
        end)

        inst:DoTaskInTime(0, function()
            print(string.format("[DST_EVENT] %s entrou no servidor", nome_jogador))
        end)

        inst:ListenForEvent("shardtransition", function(_, data)
            local destino = (data and data.to) or "desconhecido"
            print(string.format("[DST_EVENT] %s mudou para o shard: %s", nome_jogador, destino))
        end)

        inst:ListenForEvent("ms_playerleft", function()
            print(string.format("[DST_EVENT] %s saiu do servidor", nome_jogador))
        end)
    end)

    if not ok then
        print("[DST_DiscordCommandMod][ERRO] em AddPlayerPostInit: " .. tostring(err))
    end
end)

-- Removei a parte de ouvir eventos de queimar e destruir para evitar flood e crashes

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
