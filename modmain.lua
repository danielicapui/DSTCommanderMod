print("[DST_DiscordCommandMod] mod carregado")

local GLOBAL = GLOBAL

-- Lista de bosses identificados por vida alta e som de morte (não usado diretamente aqui, mas pode usar se quiser)
local bosses = {}
for k, v in pairs(GLOBAL.Prefabs) do
    if v and v.deathsound and v.health and v.health.maxhealth and v.health.maxhealth >= 2000 then
        bosses[k] = true
    end
end

AddPlayerPostInit(function(inst)
    -- Só roda no servidor (master shard)
    if not GLOBAL.TheWorld or not GLOBAL.TheWorld.ismastersim then
        return
    end

    local ok, err = GLOBAL.pcall(function()
        -- Usa o nome do personagem para mostrar (vai atualizar dentro dos eventos quando necessário)
        local nome_jogador = inst:GetDisplayName() or "??"
        local nome_char = nome_jogador

        inst:ListenForEvent("say", function(_, data)
            if data and data.message then
                -- Ignorar mensagens do bot e NPC Charlie para evitar flood e loops
                if nome_char ~= "Charlie" and not string.find(data.message, "%[DISCORD%]") then
                    local shard = GLOBAL.TheWorld and (GLOBAL.TheWorld.ismastersim and "Master" or "Caves") or "??"
                    GLOBAL.print(string.format("[DST_CHAT][%s] %s: %s", shard, nome_jogador, data.message))
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
            GLOBAL.print(string.format("[DST_EVENT] %s morreu (causa: %s)", nome_jogador, causa))
        end)

        inst:ListenForEvent("ms_respawnedfromghost", function(_, data)
            if data and data.source and data.source.GetDisplayName then
                inst.revivido_por = data.source:GetDisplayName()
            end
        end)

        inst:ListenForEvent("ms_playerspawn", function()
            if inst.revivido_por then
                GLOBAL.print(string.format("[DST_EVENT] %s foi revivido por %s", nome_jogador, inst.revivido_por))
                inst.revivido_por = nil
            else
                GLOBAL.print(string.format("[DST_EVENT] %s renasceu", nome_jogador))
            end
        end)

        -- Entrada no servidor com delay zero para garantir nome carregado
        inst:DoTaskInTime(0, function()
            local nome = inst:GetDisplayName() or "??"
            GLOBAL.print(string.format("[DST_EVENT] %s entrou no servidor", nome))
        end)

        inst:ListenForEvent("shardtransition", function(_, data)
            local destino = (data and data.to) or "desconhecido"
            GLOBAL.print(string.format("[DST_EVENT] %s mudou para o shard: %s", nome_jogador, destino))
        end)

        -- Saída do servidor com delay zero e obtendo nome atual para evitar nome vazio
        inst:ListenForEvent("ms_playerleft", function()
            inst:DoTaskInTime(0, function()
                local nome = inst:GetDisplayName() or "??"
                GLOBAL.print(string.format("[DST_EVENT] %s saiu do servidor", nome))
            end)
        end)

        -- Opcional: escuta mensagens de sistema (sem loop com prefixo [DISCORD])
        inst:ListenForEvent("ms_systemmessage", function(_, data)
            if data and data.message and not string.find(data.message, "%[DISCORD%]") then
                GLOBAL.print(string.format("[DST_EVENT] %s", data.message))
            end
        end)
    end)

    if not ok then
        GLOBAL.print("[DST_DiscordCommandMod][ERRO] em AddPlayerPostInit: " .. tostring(err))
    end
end)

AddSimPostInit(function()
    local function init()
        if GLOBAL.TheWorld then
            local shard = GLOBAL.TheWorld.ismastersim and "Master" or "Caves"
            if GLOBAL.TheShard and GLOBAL.TheShard.GetShardId then
                shard = GLOBAL.TheShard:GetShardId() or shard
            end
            GLOBAL.print(string.format("[DST_DiscordCommandMod] ativo no shard %s; chat prefixado com [DST_CHAT]", shard))
        else
            GLOBAL.TheWorld:DoTaskInTime(0.25, init)
        end
    end
    init()
end)
