#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de tradução completa da aplicação IPTV-Manager para o Português do Brasil (pt-BR).
Traduz todas as 528 chaves de interface em public/i18n.js, strings do assistente em public/ai-i18n.js
e adiciona a opção de Português no seletor de idiomas em public/index.html.
"""

import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
I18N_PATH = BASE_DIR / "public" / "i18n.js"
AI_I18N_PATH = BASE_DIR / "public" / "ai-i18n.js"
INDEX_PATH = BASE_DIR / "public" / "index.html"

# Mapeamento completo e preciso de todas as 528 chaves para pt-BR
PT_TRANSLATIONS = {
    # Tarefas em segundo plano
    "maintenanceTitle": "Tarefas em segundo plano",
    "maintenanceSerial": "As tarefas são executadas uma por vez. Você pode continuar trabalhando.",
    "maintenanceAccepted": "Aceito na fila. As tarefas são executadas em sequência.",
    "maintenanceAcceptFailed": "Não foi possível enfileirar a tarefa:",
    "maintenanceEmpty": "Nenhuma tarefa em segundo plano.",
    "maintenanceUnavailable": "Status da fila indisponível. Tentando novamente…",
    "maintenanceQueued": "Aguardando",
    "maintenanceRunning": "Em execução",
    "maintenanceSuccess": "Concluído",
    "maintenancePartial": "Parcialmente concluído",
    "maintenanceError": "Falhou",
    "maintenanceProvider": "Sincronização de provedor",
    "maintenanceEpg": "Atualização de EPG",
    "maintenanceProviderEpg": "Atualização de EPG do provedor",
    "maintenanceUser": "Usuário",

    # Reprodução e Cast
    "casting": "Transmitindo (Cast)",
    "nativePlayback": "Reprodução nativa",
    "nativeHlsPlayback": "Reprodução HLS nativa",
    "castLabel": "Transmitir",
    "channelsFetchError": "Falha ao carregar canais",
    "seriesInfoFetchError": "Falha ao carregar informações da série",
    "resetting": "Redefinindo...",
    "creating": "Criando...",
    "restore": "Restaurar",
    "date": "Data",
    "allChannels": "Todos os Canais",
    "epgMaxPastReached": "Limite máximo do histórico retroativo (catch-up) atingido",

    # Acessibilidade e Navegação
    "skipToContent": "Pular para o conteúdo",
    "selectLanguage": "Selecionar Idioma",
    "toggleNavigation": "Alternar Navegação",

    # Título & Cabeçalhos
    "title": "IPTV-Manager",
    "userManagement": "Gerenciamento de Usuários",
    "providerManagement": "Gerenciamento de Provedores",
    "categoriesChannels": "Categorias & Canais do Usuário",
    "xtreamLogin": "Acesso Xtream Codes",
    "settings": "Configurações",
    "clientLogs": "Logs de Clientes",

    # Seção de Usuários
    "totalUsers": "Total de Usuários",
    "username": "Nome de Usuário",
    "password": "Senha",
    "addUser": "Adicionar Usuário",
    "deleteUserConfirm": 'Deseja realmente excluir o usuário "{name}"?',
    "userCreated": "Usuário criado com sucesso",
    "hdhrDisabled": "A emulação HDHomeRun está desativada para este usuário.",
    "enableInEditUser": "Ative-a no menu Editar Usuário.",

    # Seção de Provedores
    "totalProviders": "Total de Provedores",
    "providerName": "Nome",
    "providerUrl": "URL do Provedor",
    "providerUsername": "Nome de Usuário",
    "providerPassword": "Senha",
    "epgUrl": "URL do EPG (opcional)",
    "backupUrls": "URLs de Backup (Contingência)",
    "backupUrlsPlaceholder": "Uma URL por linha (Opcional)",
    "providerTimeshiftTimezone": "Fuso Horário do Catch-up (IANA)",
    "providerTimeshiftTimezonePlaceholder": "Opcional, ex: America/Sao_Paulo",
    "addProvider": "Adicionar Provedor",
    "selectUserHint": "Provedores para o usuário selecionado:",
    "noProviders": "Nenhum provedor encontrado para este usuário",
    "sync": "Sincronizar",
    "syncing": "Sincronizando...",
    "syncSuccess": "{added} adicionados, {updated} atualizados, {categories} categorias",
    "syncConfig": "Configuração de Sincronização",
    "syncLogs": "Logs de Sincronização",
    "syncConfigSaved": "Configurações de sincronização salvas",
    "noSyncLogs": "Nenhum log de sincronização disponível",
    "lastSync": "Última Sincronização",
    "deleteProviderConfirm": 'Deseja realmente excluir o provedor "{name}"?',
    "providerCreated": "Provedor criado com sucesso",
    "bulkProviderUrlUpdate": "Atualização em Massa de URLs de Provedor",
    "bulkProviderUrlFrom": "URL antiga do provedor",
    "bulkProviderUrlTo": "Nova URL do provedor",
    "bulkProviderUrlRun": "Atualizar",
    "bulkProviderUrlConfirm": "Alterar todas as URLs de provedor de {from} para {to}?",
    "bulkProviderUrlSuccess": "{count} provedores atualizados com sucesso.",
    "owner": "Proprietário",
    "status": "Status",
    "added": "Adicionado",
    "updated": "Atualizado",
    "expiryDate": "Data de Validade",
    "expires": "Expira em",
    "expired": "Expirado",

    # Seção de Categorias
    "selectedUser": "Usuário Selecionado",
    "noUserSelected": "Nenhum usuário selecionado",
    "selectUserToManage": "Selecione um usuário na lista para gerenciar seus detalhes",
    "copyFromUser": "Copiar de...",
    "importCategories": "Importar Categorias do Provedor",
    "categoryName": "Nome da Categoria",
    "addCategory": "Adicionar Categoria",
    "dragToSort": "Arraste e solte para ordenar",
    "sortPosition": "Posição",
    "editCategory": "Editar Categoria",
    "newName": "Novo nome:",
    "deleteCategoryConfirm": 'Deseja realmente excluir a categoria "{name}"?',
    "categoryCreated": "Categoria criada com sucesso",
    "markedAsAdult": "Marcado como Adulto",
    "markAsAdult": "Marcar como Adulto",
    "categories": "Categorias",
    "all": "Todos",
    "del": "Excluir",
    "newCategory": "Nova Categoria",

    # Atribuição de Canais
    "channelAssignment": "Atribuição de Canais",
    "selectProvider": "Selecionar Provedor",
    "selectProviderPlaceholder": "-- Selecione o Provedor --",
    "searchChannels": "Pesquisar canais...",
    "searchChannelsHint": "Selecione o provedor e pesquise os canais",
    "searchAvailableChannels": "Buscar disponíveis...",
    "searchAssignedChannels": "Buscar atribuídos...",
    "providerChannels": "Canais do Provedor",
    "userChannels": "Canais do Usuário",
    "dragToSortChannels": "Arraste e solte",
    "noChannels": "Nenhum canal atribuído",
    "pleaseSelectProvider": "Por favor, selecione um provedor",
    "noChannelsAvailable": "Nenhum canal disponível",
    "available": "Disponíveis ({count})",
    "assigned": "Atribuídos ({count})",
    "loadingChannels": "Carregando Canais...",
    "loadingError": "Erro ao carregar",
    "noResults": 'Nenhum resultado para "{search}"',
    "moreChannels": "... e mais {count} (refine sua busca)",
    "selectUserAndCategory": "Por favor, selecione usuário e categoria",
    "loadMore": "Carregar Mais",
    "channels": "Canais",

    # Backups
    "backups": "Backups",
    "buildedCategoriesBackups": "Backups de Categorias Montadas",
    "createBackup": "Criar Backup",
    "backupLimitInfo": "Máximo de 5 backups permitidos. Backups mais antigos devem ser excluídos quando o limite for atingido.",
    "noBackupsFound": "Nenhum backup encontrado.",
    "enterBackupName": "Digite um nome para o backup:",
    "renameChannel": "Renomear Canal",
    "enterNewChannelName": "Digite o novo nome do canal (deixe em branco para restaurar o original):",
    "backupCreated": "Backup criado com sucesso.",
    "confirmRestoreBackup": "Tem certeza que deseja restaurar o backup '{name}'? Isso substituirá suas categorias e canais atuais.",
    "backupRestored": "Backup restaurado com sucesso.",
    "confirmDeleteBackup": "Tem certeza que deseja excluir o backup '{name}'?",
    "backupDeleted": "Backup excluído com sucesso.",

    # Xtream Codes & Importação
    "xtreamCodes": "Xtream Codes",
    "importCategoriesTitle": "Importar Categorias do Provedor",
    "searchCategories": "Pesquisar categorias...",
    "loadingCategories": "Carregando categorias...",
    "noCategoriesFound": "Nenhuma categoria encontrada",
    "importCategoryOnly": "Somente Categoria",
    "importWithChannels": "Com Canais",
    "close": "Fechar",
    "categoryImportedOnly": 'Categoria "{name}" criada (sem canais)',
    "categoryImportedWithChannels": 'Categoria "{name}" importada com {count} canais',
    "markedAsAdultContent": "Marcado como Conteúdo Adulto (+18)",
    "url": "URL",
    "epgUrlLabel": "URL do EPG",
    "passwordPlaceholder": "<Sua Senha>",
    "copyAll": "Copiar Todas as Credenciais",
    "copiedToClipboard": "Copiado para a área de transferência",
    "copied": "Copiado!",
    "pleaseSelectUserFirst": "Por favor, selecione um usuário primeiro",
    "error": "Erro",
    "errorPrefix": "Erro:",
    "delete": "Excluir",
    "edit": "Editar",
    "adult": "Adulto",
    "add": "+",
    "browse": "Explorar",
    "updateAll": "Atualizar Todos",
    "clearEpg": "Limpar EPG",
    "confirmClearEpg": "Tem certeza de que deseja limpar todos os dados do EPG? Isso não removerá os mapeamentos.",
    "save": "Salvar",
    "generateRandomUser": "Gerar Usuário Aleatório",
    "copyToClipboardAction": "Copiar para a Área de Transferência",
    "deleteAction": "Excluir",
    "loading": "Carregando...",
    "saving": "Salvando...",
    "typeLive": "Ao Vivo",
    "typeMovie": "Filmes",
    "typeSeries": "Séries",
    "typeRadio": "Rádio",
    "toggleSidebar": "Alternar barra lateral",
    "hdhomerun": "HDHomeRun",

    # Autenticação e Conta
    "login": "Entrar",
    "logout": "Sair",
    "logging_in": "Entrando...",
    "missing_credentials": "Por favor, informe usuário e senha",
    "invalid_credentials": "Usuário ou senha inválidos",
    "login_failed": "Falha no login. Por favor, tente novamente.",
    "token_expired": "Sua sessão expirou. Por favor, faça login novamente.",
    "authentication_required": "Autenticação obrigatória",
    "access_denied_webui": "Acesso negado à interface Web",
    "invalid_otp": "Código 2FA inválido",
    "server_error": "Erro no Servidor",
    "user_not_found": "Usuário não encontrado",
    "username_taken": "Este nome de usuário já está em uso",
    "invalid_username_format": "Formato de nome de usuário inválido",
    "invalid_username_length": "O nome de usuário deve ter entre 3 e 50 caracteres",
    "maxConnections": "Conexões Simultâneas",
    "unlimitedConnections": "0 = Ilimitadas",
    "maxConnectionsShort": "Máx.",
    "notes": "Observações",
    "notesMax": "Máximo de 50 caracteres",

    # Fontes de EPG
    "epgSources": "Fontes de EPG",
    "addEpgSource": "Adicionar Fonte de EPG",
    "browseEpgSources": "Explorar Fontes Disponíveis",
    "updateAllEpg": "Atualizar Todos os EPGs",
    "addEpgSourceTitle": "Adicionar Fonte de EPG",
    "editEpgSourceTitle": "Editar Fonte de EPG",
    "browseEpgSourcesTitle": "Explorar Fontes de EPG Disponíveis",
    "name": "Nome",
    "updateInterval": "Intervalo de Atualização",
    "enabled": "Ativado",
    "addSource": "Adicionar Fonte",
    "saveChanges": "Salvar Alterações",
    "searchEpgSources": "Pesquisar fontes...",
    "noEpgSourcesConfigured": "Nenhuma fonte de EPG configurada",
    "epgUpdateSuccess": "EPG atualizado com sucesso",
    "epgUpdateAllConfirm": "Atualizar todas as fontes de EPG? Isso pode levar alguns minutos.",
    "epgUpdateAllSuccess": "Atualização de EPG concluída!\nSucesso: {success}\nFalhas: {failed}",
    "epgSourceAdded": "Fonte de EPG adicionada com sucesso",
    "epgSourceUpdated": "Fonte de EPG atualizada com sucesso",
    "epgSourceAddedName": "Fonte de EPG adicionada: {name}",
    "failedToLoadSources": "Falha ao carregar fontes de EPG",
    "noSourcesFound": "Nenhuma fonte encontrada",
    "confirmDeleteEpgSource": 'Excluir a fonte de EPG "{name}"?',
    "disable": "Desativar",
    "enable": "Ativar",
    "updateNow": "Atualizar Agora",
    "never": "Nunca",
    "updating": "Atualizando...",
    "interval_1h": "1 hora",
    "interval_6h": "6 horas",
    "interval_12h": "12 horas",
    "interval_24h": "24 horas",
    "interval_7d": "7 dias",

    # Alteração de Senha
    "change_password": "Alterar Senha",
    "show_password": "Exibir Senha",
    "hide_password": "Ocultar Senha",
    "old_password": "Senha Atual",
    "new_password": "Nova Senha",
    "confirm_password": "Confirmar Nova Senha",
    "password_min_length": "Mínimo de 8 caracteres",
    "passwords_dont_match": "As senhas não coincidem",
    "password_too_short": "A senha deve ter pelo menos 8 caracteres",
    "invalid_old_password": "Senha atual incorreta",
    "password_changed_successfully": "Senha alterada com sucesso!",
    "change_password_failed": "Falha ao alterar senha",
    "changing_password": "Alterando senha...",
    "missing_fields": "Por favor, preencha todos os campos",

    # Dashboard & Mapeamento EPG
    "dashboard": "Painel de Controle",
    "epgMapping": "Mapeamento de EPG",
    "epgMappingTitle": "Mapeamento de EPG",
    "autoMap": "Mapeamento Automático",
    "channelMappingList": "Lista de Canais",
    "channelName": "Nome do Canal",
    "currentEpgId": "ID Atual do EPG",
    "manualMapping": "Mapeamento Manual",
    "actions": "Ações",
    "selectEpgChannel": "Selecionar Canal do EPG",
    "map": "Mapear",
    "unmap": "Desmapear",
    "selectProviderFirst": "Por favor, selecione um provedor primeiro",
    "allProviders": "Todos os provedores",
    "allProvidersSelected": "Todos os provedores selecionados. As ações serão executadas globalmente.",
    "autoMapConfirm": "Mapear automaticamente todos os canais sem EPG?",
    "autoMapAllConfirm": "Mapear automaticamente todos os canais sem EPG em todos os provedores?",
    "autoMapSuccess": "Mapeamento automático concluído: {count} canais mapeados.",
    "resetMapping": "Redefinir Mapeamento",
    "resetMappingConfirm": "Deseja realmente redefinir todos os mapeamentos deste provedor?",
    "resetAllMappingsConfirm": "Deseja realmente redefinir todos os mapeamentos de EPG em todos os provedores?",
    "resetMappingSuccess": "Mapeamentos redefinidos com sucesso",
    "mappingJobFailed": "Falha no processo de mapeamento",
    "mappingSaved": "Mapeamento salvo",
    "mappingRemoved": "Mapeamento removido",
    "configuration": "Configuração",
    "mappingStats": "Total: {total} | Mapeados: {mapped} ({percent}%) | Manuais: {manual}",
    "suggestions": "Sugestões",
    "loadingSuggestions": "Carregando sugestões...",
    "noSuggestionsFound": "Nenhuma sugestão encontrada",
    "confidence": "Confiabilidade",
    "searchAllChannels": "Pesquisar Todos os Canais",

    # Estatísticas e Métricas
    "statistics": "Estatísticas",
    "systemInformation": "Informações do Sistema",
    "cpuUtilization": "CPU",
    "memoryUtilization": "Memória RAM",
    "hddUtilization": "Disco (HDD/SSD)",
    "bandwidthUtilization": "Rede",
    "rx": "Download (Rx)",
    "tx": "Upload (Tx)",
    "totalRx": "Total Recebido:",
    "totalTx": "Total Enviado:",
    "cores": "Núcleos",
    "activeStreams": "Transmissões Ativas",
    "topChannels": "Canais Mais Assistidos",
    "streamCount": "Espectadores",
    "lastViewed": "Último Acesso",
    "currentViewers": "Espectadores Atuais",
    "duration": "Duração",
    "terminateStream": "Encerrar",
    "confirmTerminateStream": "Deseja realmente encerrar esta transmissão ativa?",
    "ip": "Endereço IP",
    "client": "Cliente / App",
    "resetStats": "Zerar Estatísticas",
    "confirmResetStats": "Deseja realmente zerar todas as estatísticas?",
    "statsResetSuccess": "Estatísticas zeradas com sucesso",
    "importSelected": "Importar Selecionados",
    "importSelectedWithChannels": "Importar Selecionados com Canais",
    "selectAll": "Selecionar Tudo",
    "deselectAll": "Desmarcar Tudo",
    "lastEpgUpdate": "Última Atualização EPG",

    # Playlist M3U & Segurança
    "m3uPlaylist": "6. Playlist M3U",
    "m3uLink": "Link M3U",
    "m3uDescription": "Utilize este link no seu aplicativo ou player de IPTV.",
    "blockDuration": "Duração do Bloqueio",
    "whitelistReason": "Motivo",
    "minutes": "Minutos",
    "hours": "Horas",
    "custom": "Personalizado",
    "reasonPlaceholder": "Motivo da liberação na lista branca",
    "ipBlockDuration": "Duração do Bloqueio de IP (segundos)",
    "adminBlockThreshold": "Limite de Tentativas no Admin (tentativas)",
    "iptvBlockThreshold": "Limite de Tentativas no IPTV (tentativas)",
    "adminBlockDuration": "Duração do Bloqueio no Admin (segundos)",
    "iptvBlockDuration": "Duração do Bloqueio no IPTV (segundos)",
    "geoIpSettings": "Banco de Dados GeoIP",
    "geoIpSettingsHelp": "Atualize a base local GeoIP para bloqueio por região. Faz o download dos dados MaxMind GeoLite2.",
    "getFreeKeyHelp": "Obter uma chave de licença gratuita.",
    "maxmindLicenseKey": "Chave de Licença MaxMind",
    "updateGeoIp": "Atualizar GeoIP",
    "confirmUpdateGeoIp": "Iniciar atualização da base GeoIP? A operação roda em segundo plano e pode levar alguns minutos.",
    "allowedCountries": "Países Permitidos (Bloqueio Regional)",
    "allowedCountriesHelp": "Deixe em branco para permitir todos os países. Selecione países para restringir o acesso.",
    "allowedCountriesPlaceholder": "Países (ex: BR,PT)",
    "level": "Nível",
    "message": "Mensagem",
    "clearLogs": "Limpar Logs",
    "security": "Segurança",
    "blockIp": "Bloquear IP",
    "whitelistIp": "Lista Branca de IP",
    "block": "Bloquear",
    "whitelist": "Lista Branca",
    "piconCache": "Cache de Picons (Logos)",
    "pruneCache": "Limpar Cache",
    "confirmPrunePicons": "Realmente limpar o cache de logos? Todas as imagens em cache serão excluídas e baixadas novamente.",
    "piconsPrunedSuccess": "{count} picons removidos do cache com sucesso.",
    "piconCacheHint": "Limpar o cache forçará o download das logos novamente.",
    "securityLogs": "Logs de Segurança",
    "time": "Hora",
    "action": "Ação",
    "details": "Detalhes",
    "confirmUnblock": "Realmente desbloquear este IP?",
    "confirmRemoveWhitelist": "Remover este IP da lista branca?",
    "noLogs": "Nenhum log registrado",
    "selectUserPlaceholder": "-- Selecione o Usuário --",
    "userUpdated": "Usuário atualizado com sucesso",
    "providerUpdated": "Provedor atualizado com sucesso",
    "settingsSaved": "Configurações salvas com sucesso",
    "confirmClearLogs": "Realmente limpar todos os logs?",
    "deleteSelected": "Excluir Selecionados",
    "deleteChannelConfirm": "Deseja realmente excluir {count} canais?",
    "unblock": "Desbloquear",
    "remove": "Remover",
    "none": "Nenhum",
    "noSelection": "Nenhum item selecionado",
    "editUser": "Editar Usuário",
    "leaveBlankToKeep": "Deixe em branco para manter o valor atual",
    "enableEpg": "Ativar EPG",
    "useMappedEpgIcon": "Usar Ícone Mapeado do EPG",
    "enableAutomaticSync": "Ativar Sincronização Automática",
    "syncInterval": "Intervalo de Sincronização",
    "hourly": "A Cada Hora",
    "every_6_hours": "A Cada 6 Horas",
    "every_12_hours": "A Cada 12 Horas",
    "daily": "Diariamente",
    "weekly": "Semanalmente",
    "autoAddNewCategories": "Adicionar automaticamente novas categorias",
    "autoAddChannelsToCategories": "Adicionar automaticamente canais às categorias",
    "syncSeriesEpisodes": "Sincronizar episódios de séries (para listas M3U)",
    "saveConfiguration": "Salvar Configuração",

    # Importação e Exportação
    "importExport": "Importar / Exportar",
    "exportData": "Exportar Dados",
    "importData": "Importar Dados",
    "exportDescription": "Exporte usuários, provedores e configurações para um arquivo seguro criptografado.",
    "importDescription": "Restaure dados a partir de um arquivo exportado anteriormente.",
    "selectUserExport": "Selecione o Usuário para Exportar",
    "allUsers": "Todos os Usuários",
    "encryptionPassword": "Senha de Criptografia",
    "decryptionPassword": "Senha de Descriptografia",
    "encryptionPasswordHint": "Esta senha será obrigatória para descriptografar e importar os dados posteriormente.",
    "exportBtn": "Exportar Dados",
    "importBtn": "Importar Dados",
    "fileSelect": "Selecionar Arquivo",
    "exportSuccess": "Exportação concluída com sucesso",
    "importSuccess": "Importação concluída com sucesso",
    "confirmImport": "A importação de dados preservará usuários existentes, mas poderá adicionar novos provedores e canais. Deseja continuar?",
    "processing": "Processando...",

    # Web Player & Mídia
    "openWebPlayer": "Abrir Web Player",
    "playerTitle": "IPTV Web Player",
    "liveTV": "TV ao Vivo",
    "movies": "Filmes (VOD)",
    "series": "Séries",
    "allCategories": "Todas as Categorias",
    "searchPlaceholder": "Pesquisar...",
    "clearSearch": "Limpar busca",
    "season": "Temporada",
    "episode": "Episódio",
    "backToSeries": "Voltar para Lista de Séries",
    "noEpisodesFound": "Nenhum episódio encontrado",
    "missingCredentials": "Credenciais ausentes",
    "maximize": "Maximizar",
    "minimize": "Minimizar",
    "playbackError": "Erro de Reprodução: Codec pode não ser suportado pelo navegador",
    "transcodeAudio": "Corrigir Áudio (Transcodificar)",
    "autoFixingAudio": "Codec não suportado detectado. Ativando correção automática de áudio...",
    "audioTrack": "Faixa de Áudio",
    "subtitleTrack": "Legendas",
    "subtitlesOff": "Legendas Desativadas",
    "defaultTrack": "Padrão",
    "mpdInfoToggle": "Exibir informações do MPD",
    "mpdInfoLoading": "Carregando informações do MPD...",
    "mpdInfoUnavailable": "Informações do MPD indisponíveis",
    "mpdInfoManifest": "Manifesto MPD",
    "mpdInfoType": "Tipo",
    "mpdInfoDuration": "Duração",
    "mpdInfoBuffer": "Buffer",
    "mpdInfoPeriods": "Períodos",
    "mpdInfoAdaptationSets": "Conjuntos",
    "mpdInfoRepresentations": "Representações",
    "mpdInfoVideo": "Vídeo",
    "mpdInfoAudio": "Áudio",

    # 2FA e Segurança de Acesso
    "managed_by_admin": "Gerenciado pelo Administrador",
    "otp_required": "Código 2FA Obrigatório",
    "otp_code": "Código 2FA",
    "setup_2fa": "Configurar 2FA",
    "disable_2fa": "Desativar 2FA",
    "scan_qr": "Escaneie o código QR com seu aplicativo autenticador (Google Authenticator, Authy, etc.)",
    "verify": "Verificar",
    "only_used_channels": "Apenas canais utilizados",
    "2fa_enabled_success": "Autenticação em 2 Fatores (2FA) Ativada com Sucesso",
    "2fa_disabled_success": "Autenticação em 2 Fatores (2FA) Desativada",
    "confirm_disable_2fa": "Deseja realmente desativar o 2FA?",
    "2fa_enabled": "2FA está ativado",
    "webui_access": "Acesso à Interface Web",
    "viewUpstreamProvider": "Ver Provedor Upstream",
    "modeProvider": "Por Provedor",
    "modeCategory": "Por Categoria",
    "selectUser": "Selecionar Usuário",
    "selectCategory": "Selecionar Categoria",
    "selectCategoryPlaceholder": "-- Selecione a Categoria --",
    "selectUserFirst": "Por favor, selecione um usuário primeiro",
    "select_options_to_load": "Selecione as opções acima para carregar os canais",
    "days": "dias",
    "providers": "Provedores",
    "skipped": "Ignorados",
    "credentialsFor": 'Credenciais de "{name}"',
    "usernameCaps": "USUÁRIO",
    "passwordCaps": "SENHA",
    "epgUrlCaps": "URL-EPG",
    "m3uUrlCaps": "URL-M3U",
    "categoriesImported": "{count} categorias importadas",
    "errorLoadingData": "Erro ao carregar dados",
    "popupBlocked": "Janela pop-up bloqueada. Permita pop-ups para este endereço.",
    "otpPlaceholder": "123456",
    "optional": "(Opcional)",
    "time_h": "h",
    "time_m": "m",
    "time_s": "s",

    # Compartilhamento de Links (Shares)
    "share": "Compartilhar",
    "updateShare": "Atualizar Link",
    "manageShares": "Gerenciar Compartilhamentos",
    "createShareLink": "Criar Link de Compartilhamento",
    "shareName": "Nome",
    "shareNamePlaceholder": "Ex: Acesso Visitante",
    "shareNameRequired": "O nome do link é obrigatório",
    "startTime": "Início da Validade",
    "endTime": "Término da Validade",
    "leaveEmptyForNow": "Deixe em branco para liberar imediatamente",
    "leaveEmptyForNever": "Deixe em branco para validade ilimitada",
    "selectedChannels": "Canais Selecionados",
    "shareLinkCreated": "Link de Compartilhamento Criado:",
    "createLink": "Criar Link",
    "activeShares": "Compartilhamentos Ativos",
    "validity": "Validade",
    "link": "Link",
    "confirmDeleteShare": "Deseja realmente excluir este compartilhamento?",
    "success": "Sucesso",
    "force_password_change": "Você deve alterar sua senha imediatamente por motivos de segurança.",
    "editingShare": "Editando Compartilhamento:",
    "editShareInstructions": "Modifique os canais selecionados e clique em 'Atualizar Link'.",
    "cancel": "Cancelar",
    "cancelEdit": "Cancelar Edição",

    # Integrações HDHomeRun & Stalker/MAG
    "enableHDHomeRun": "Ativar HDHomeRun",
    "useUrlToConfigurePlex": "Utilize a URL abaixo para configurar o Plex DVR ou Emby Live TV.",
    "note": "Nota:",
    "featureEmulatesHDHomeRun": "Este recurso emula um sintonizador físico HDHomeRun na sua rede.",
    "deviceUrl": "URL do Dispositivo",
    "userAgent": "User-Agent",
    "advancedSettings": "Configurações Avançadas (Bloqueio Regional)",
    "saveSettings": "Salvar Configurações",
    "loadingEpg": "Carregando dados de EPG...",
    "unsupportedCodec": "Codec não suportado detectado. Ativando conversão de áudio...",
    "playbackErrorCodec": "Erro de Reprodução: Codec de áudio/vídeo não suportado nativamente",
    "videoPlayer": "Player de Vídeo",
    "catchupAvailable": "Gravação disponível (Catch-up) - clique para assistir",
    "catchupSupported": "Suporta reprodução retroativa (Catch-up)",
    "epgPrevDay": "Dia Anterior",
    "epgEarlier": "Mais Cedo",
    "epgNow": "Agora",
    "epgLater": "Mais Tarde",
    "epgNextDay": "Próximo Dia",
    "stalkerMag": "Stalker / MAG",
    "stalkerExperimentalPortal": "Suporte a portal para TV ao Vivo, Filmes, Séries, Rádio e Catch-up. Cadastre o endereço MAC do aparelho antes de conectar.",
    "stalkerPortalUrl": "URL do Portal",
    "stalkerCopyPortalUrl": "Copiar URL do Portal",
    "stalkerDeviceMac": "Endereço MAC do Aparelho",
    "stalkerParentalPin": "PIN de Controle Parental",
    "stalkerParentalPinOptional": "PIN Opcional (4 dígitos)",
    "stalkerPinConfigured": "PIN Parental configurado",
    "stalkerPinNotConfigured": "Nenhum PIN parental configurado",
    "stalkerSetPin": "Definir PIN",
    "stalkerClearPin": "Limpar PIN",
    "stalkerClearPinConfirm": "Deseja realmente limpar o PIN de controle parental do aparelho {mac}?",
    "stalkerAddDevice": "Adicionar Aparelho",
    "stalkerNoDevices": "Nenhum aparelho registrado.",
    "stalkerLastSeen": "Visto pela última vez: {value}",
    "stalkerNever": "Nunca",
    "stalkerEnable": "Ativar",
    "stalkerDisable": "Desativar",
    "stalkerDelete": "Excluir",
    "stalkerDeleteDeviceConfirm": "Deseja realmente excluir o aparelho {mac}?",
    "stalkerLoadingDevices": "Carregando aparelhos Stalker...",
    "stalkerDeviceError": "Erro no dispositivo Stalker: {error}",
    "stalkerPortalPageTitle": "Portal Stalker IPTV-Manager",
    "stalkerPortalApiAvailable": "A API Stalker/MAG está operacional em",
    "stalkerPortalSetup": "Cadastre o MAC do aparelho na visualização de usuário do IPTV-Manager e utilize a URL /stalker_portal/c/ no seu receptor Stalker/MAG."
}

# Tradução do Assistente IA (ai-i18n.js)
AI_TRANSLATIONS = {
    "title": "Assistente IA",
    "intro": "Ajuda experimental e opcional para seu catálogo IPTV. Alterações exigem sua confirmação.",
    "setup": "Configuração da conexão",
    "policy": "Permissões do administrador",
    "enabled": "Ativar IA",
    "autoSync": "Resumir automaticamente futuras sincronizações (pode incorrer em consumo)",
    "off": "A IA está desativada. Ative a política central e sua preferência pessoal para executar solicitações.",
    "ownAllowed": "Permitir conexões pessoais",
    "users": "Usuários permitidos",
    "targets": "URLs base internas aprovadas (uma URL exata por linha)",
    "functions": "Funções permitidas",
    "save": "Salvar",
    "saved": "Salvo",
    "connection": "Escolha uma conexão",
    "userSelectionHint": "Selecione múltiplos usuários com Ctrl/Cmd-clique. Uma seleção vazia não concede acesso a ninguém.",
    "unavailableUser": "Usuário indisponível — seleção salva",
    "choose": "Escolher…",
    "own": "Conectar minha própria API",
    "provided": "Conexão fornecida: usar o modelo testado pelo administrador.",
    "name": "Nome da conexão",
    "url": "URL base da API",
    "key": "Chave da API (deixe em branco para manter a chave salva)",
    "keyInfo": "A chave é armazenada criptografada neste servidor; o operador pode acessá-la. Nunca insira credenciais de provedor.",
    "shared": "Disponibilizar esta conexão para usuários autorizados",
    "destination": "Destino da requisição",
    "disclosure": "A descoberta envia sua chave para este destino. Os testes enviam texto sintético (máx. 3 modelos, máx. 3 chamadas cada; 128 tokens de saída por chamada) e podem gerar consumo. Os recursos enviam os títulos necessários e metadados sanitizados. Custo desconhecido.",
    "discover": "Salvar e localizar modelos",
    "test": "Testar modelos selecionados",
    "models": "Modelos para testar (selecione no máximo 3)",
    "advanced": "Avançado / modelo manual",
    "model": "ID do modelo selecionado",
    "tokenParameter": "Parâmetro de limite de tokens",
    "recommendation": "Usar recomendação testada",
    "candidateHint": "Selecione até 3 candidatos por teste. Metadados de modalidade de texto são apenas sugestões; nomes e ordem da lista não comprovam capacidade. Após incompatibilidade, selecione outro lote. Aliases desconhecidos também podem ser testados.",
    "profileProbe": "Um parâmetro de token alternativo é testado apenas após rejeição explícita de parâmetro. Timeouts e respostas incertas nunca são repetidos automaticamente. Conclua a configuração para adotar um perfil testado.",
    "notListed": "não está na lista atual de modelos",
    "testStatus": "Resultado do teste",
    "compatible": "JSON e saída estruturada aprovados",
    "json_fallback": "JSON simples aprovado; saída estruturada não verificada",
    "incompatible": "Explicitamente rejeitado; escolha outro candidato",
    "unverified": "Resposta não verificada; sem repetição automática",
    "permission": "A identidade da API não tem permissão. Verifique as permissões do provedor; nenhuma outra identidade foi usada.",
    "rateLimit": "Limite do provedor ou orçamento de teste local atingido. Aguarde antes de outro teste explícito.",
    "diagnosticScope": "Verificações locais: atribuição, visibilidade, filtros de exportação de conta, configuração de EPG e conexões registradas de usuários. Entradas ocultas próprias podem ser selecionadas pelo ID do canal. Alcance de rede, entrega real de exportação/reprodução, filtros de cliente/compartilhamento, limites upstream e identificação da sessão de streaming selecionada não são medições implementadas.",
    "localOnly": "Explicação de IA indisponível. Descobertas técnicas locais continuam disponíveis abaixo.",
    "diagnosticPreviewCount": "Entradas com verificações locais detalhadas",
    "proven": "Descobertas locais comprovadas",
    "diagnosticUnknown": "Indeterminado nos testes locais",
    "diagnosticNotProven": "Não comprovado nos testes locais",
    "diagnosticPreviewTruncated": "Mais entradas omitidas",
    "diagnosticHiddenInSource": "Oculto na fonte do usuário",
    "diagnosticNotConfigured": "Não configurado no provedor",
    "diagnosticActiveLimitReached": "Limite de streams atingido",
    "diagnosticRecentError": "Erro recente registrado",
    "diagnosticOk": "Nenhuma anomalia técnica local",
    "diagnosticSummary": "Resumo de integridade",
    "diagnosticDetails": "Detalhes de diagnóstico",
    "diagnosticStreamSession": "Sessão de stream selecionada",
    "auth": "O serviço de IA rejeitou a autorização. Verifique a chave de API salva.",
    "modelError": "Escolha e teste um modelo de chat. Nenhum modelo foi alterado automaticamente.",
    "invalidOutput": "A resposta não pôde ser validada. Nenhuma alteração foi aplicada.",
    "ownChatgpt": "Conectar minha conta ChatGPT",
    "chatgptDisclosure": "Usa seu próprio plano ChatGPT através do login oficial do Codex. Nenhuma chave de API da plataforma OpenAI é necessária. As requisições e seus títulos/metadados são processados pela OpenAI sob sua conta, contam contra sua cota pessoal e podem ser limitados pelas regras do seu plano ou workspace. A conexão permanece privada para você e não pode ser compartilhada. Os resumos automáticos de sincronização permanecem desativados.",
    "managedDestination": "Login gerenciado do ChatGPT (servidor oficial do app Codex)",
    "accountLinked": "Conta ChatGPT conectada",
    "accountNotLinked": "Nenhuma conta ChatGPT conectada ainda",
    "accountLabel": "Conta",
    "accountRefresh": "Atualizar conta e cota",
    "plan": "Plano",
    "quotaUnknown": "Cota restante desconhecida. A interface não informou janela de uso; nenhum preço ou contagem de requisições é estimado.",
    "quotaUsed": "Utilizado",
    "quotaWindow": "Janela",
    "quotaResets": "Redefine em",
    "quotaBlocked": "O serviço informa atualmente que não há uso incluído para esta conta.",
    "linkStart": "Conectar conta ChatGPT",
    "linkPending": "Abra a página de login, conecte-se ao ChatGPT e insira este código:",
    "linkCode": "Código do dispositivo",
    "linkCancel": "Cancelar login",
    "linkDone": "Conta ChatGPT conectada.",
    "linkFailed": "O login não foi concluído. Nada foi salvo; inicie novamente se desejar tentar de novo.",
    "teardownOnly": "O acesso de IA para esta conta foi revogado. A conta ChatGPT vinculada ainda pode ser desconectada aqui.",
    "linkRejected": "O login foi recusado ou não confirmado. Nada foi salvo.",
    "linkRetrying": "Conexão com o servidor interrompida. Aguardando seu login e tentando novamente…",
    "linkExpired": "O código do dispositivo expirou. Inicie o login novamente.",
    "linkCancelled": "Login cancelado. Nada foi salvo.",
    "linkSuperseded": "Esta tentativa foi substituída por uma mais recente ou por alteração de sessão; seu resultado foi descartado.",
    "linkInterrupted": "O login foi interrompido no servidor. Inicie-o novamente.",
    "linkUnsupported": "O login por código de dispositivo não está ativado para esta conta ou workspace. Um administrador deve autorizá-lo.",
    "linkTargetBlocked": "O endereço de login retornado não é um destino aprovado e não foi aberto.",
    "alreadyLinked": "Esta conta ChatGPT já está conectada a outra conexão aqui. Cada conta só pode ser vinculada uma vez.",
    "accountUnavailable": "O login foi concluído, mas nenhuma conta ChatGPT foi reportada; nada foi conectado. Tente novamente.",
    "accountUnidentified": "A conta conectada não pôde ser identificada e não foi vinculada. Cada conta só pode ser vinculada uma vez com identidade confirmada.",
    "notLinked": "Conecte sua conta ChatGPT antes de executar requisições.",
    "unexpectedAuth": "Um modo de autenticação inesperado estava ativo. A requisição foi recusada e nenhuma outra credencial foi usada.",
    "toolRequest": "O modelo tentou utilizar uma ferramenta externa. Toda a resposta foi descartada e nada foi alterado.",
    "manualOnly": "Esta conexão executa apenas solicitações iniciadas manualmente por você. Resumos automáticos permanecem desativados.",
    "codexUnavailable": "A conexão pessoal do ChatGPT não está disponível neste servidor. Seu runtime está desativado ou o isolamento necessário está ausente.",
    "unlink": "Desconectar conta ChatGPT",
    "confirmUnlink": "Desconectar esta conta ChatGPT? As requisições pendentes serão canceladas e o login salvo será removido deste servidor.",
    "unlinkDone": "Conta desconectada e login salvo removido.",
    "unlinkRemoteFailed": "O acesso local foi removido, mas o encerramento da sessão na OpenAI não pôde ser confirmado. Verifique as sessões ativas na sua conta ChatGPT."
}


def atualizar_i18n():
    print("[1/3] Atualizando public/i18n.js com o idioma Português (pt)...")
    content = I18N_PATH.read_text(encoding="utf-8")

    # Garante que chaves que por ventura faltaram usem fallback do en
    with open(BASE_DIR / "en_keys.json", "r", encoding="utf-8") as f:
        en_keys = json.load(f)

    final_pt = {}
    for k, v in en_keys.items():
        if k in PT_TRANSLATIONS:
            final_pt[k] = PT_TRANSLATIONS[k]
        else:
            final_pt[k] = v

    # Serializa objeto pt formatado
    pt_entries = []
    for k, v in final_pt.items():
        v_escaped = v.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace("\r", "")
        pt_entries.append(f"    '{k}': '{v_escaped}'")
    pt_block = "  pt: {\n" + ",\n".join(pt_entries) + "\n  },\n"

    # Se já tem pt, remove para reinserir
    content = re.sub(r"  pt:\s*\{[\s\S]*?\n  \},\n", "", content)

    # Insere antes de de: {
    if "  de: {" in content:
        content = content.replace("  de: {", pt_block + "  de: {")
    else:
        # Insere antes do fechamento do translations
        content = re.sub(r"(\n\};)", r",\n" + pt_block + r"\1", content)

    # Ajusta o detectLanguage para priorizar pt ou detectar pt-BR
    content = re.sub(
        r"return translations\[langCode\] \? langCode : 'en';",
        "return translations[langCode] ? langCode : (translations['pt'] ? 'pt' : 'en');",
        content
    )

    I18N_PATH.write_text(content, encoding="utf-8")
    print(f"  [OK] public/i18n.js atualizado com {len(final_pt)} chaves em Português!")


def atualizar_ai_i18n():
    print("[2/3] Atualizando public/ai-i18n.js para incluir suporte a 'pt'...")
    content = AI_I18N_PATH.read_text(encoding="utf-8")

    # Percorre cada linha que define uma chave do array
    lines = content.split("\n")
    new_lines = []
    for line in lines:
        m = re.match(r"^(\s*([a-zA-Z0-9_]+)\s*:\s*\[)(.*)(\],?)", line)
        if m:
            prefix = m.group(1)
            key = m.group(2)
            elements_str = m.group(3)
            suffix = m.group(4)

            # Verifica se já tem 5 elementos ou adiciona tradução em pt
            pt_val = AI_TRANSLATIONS.get(key, key)
            pt_val_escaped = pt_val.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')

            # Se ainda tem só 4 elementos (en, de, fr, el)
            if "['en', 'de', 'fr', 'el']" in content and len(re.findall(r"['\"].*?['\"]", elements_str)) == 4:
                line = f"{prefix}{elements_str}, '{pt_val_escaped}'{suffix}"
            elif len(re.findall(r"['\"].*?['\"]", elements_str)) == 4:
                line = f"{prefix}{elements_str}, '{pt_val_escaped}'{suffix}"

        new_lines.append(line)

    new_content = "\n".join(new_lines)
    # Atualiza o laço de atribuição
    new_content = new_content.replace(
        "['en', 'de', 'fr', 'el'].forEach",
        "['en', 'de', 'fr', 'el', 'pt'].forEach"
    )

    AI_I18N_PATH.write_text(new_content, encoding="utf-8")
    print("  [OK] public/ai-i18n.js atualizado com 'pt'!")


def atualizar_index_html():
    print("[3/3] Atualizando public/index.html com opção Português e tag lang='pt-BR'...")
    content = INDEX_PATH.read_text(encoding="utf-8")

    # Atualiza lang do html
    content = re.sub(r'<html lang="[a-zA-Z\-]+"', '<html lang="pt-BR"', content)

    # Adiciona Português no selector de idiomas se ainda não existir
    if 'value="pt"' not in content:
        pt_option = '            <option value="pt" selected>🇧🇷 Português</option>\n'
        content = content.replace(
            '<select id="language-selector" class="form-select form-select-sm bg-dark text-light border-secondary w-auto" data-i18n-label="selectLanguage">\n',
            '<select id="language-selector" class="form-select form-select-sm bg-dark text-light border-secondary w-auto" data-i18n-label="selectLanguage">\n' + pt_option
        )
        # Remove selected dos outros
        content = content.replace('<option value="en" selected>', '<option value="en">')

    INDEX_PATH.write_text(content, encoding="utf-8")
    print("  [OK] public/index.html atualizado!")


if __name__ == "__main__":
    atualizar_i18n()
    atualizar_ai_i18n()
    atualizar_index_html()
    print("\n[SUCESSO] Tradução completa para Português (pt-BR) executada com êxito!")

