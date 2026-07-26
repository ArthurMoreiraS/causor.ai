from app.connectors.mni.profiles import known_mni_profiles, resolve_mni_profile


def test_resolve_known_profile_by_tribunal_and_grau():
    profile = resolve_mni_profile("TRF5", "1")
    assert profile is not None
    assert profile.url_endpoint == "https://pje.trf5.jus.br/pje/intercomunicacao"
    assert profile.versao == "2.2.2"


def test_resolve_is_case_insensitive_and_fails_closed():
    assert resolve_mni_profile("trf5", "1") is not None
    assert resolve_mni_profile("TJXX", "1") is None
    assert resolve_mni_profile("TRF5", "3") is None


def test_profile_is_immutable():
    profile = resolve_mni_profile("TRF5", "1")
    try:
        profile.url_endpoint = "https://x"  # type: ignore[misc]
        raised = False
    except AttributeError:
        raised = True
    assert raised


def test_todo_perfil_registrado_foi_verificado_contra_o_tribunal():
    """Falha de MNI marca a captura ``failed`` e nao cai para o agente
    (``executor.run_mni_capture_job``). Endpoint palpitado manda o advogado
    para um erro em vez do caminho que funciona — so entra aqui o que
    respondeu WSDL de verdade."""
    assert known_mni_profiles(), "tabela de perfis vazia"
    for profile in known_mni_profiles():
        assert profile.verificado is True, f"{profile.tribunal}/{profile.grau} nao verificado"
        assert profile.url_endpoint.startswith("https://")
        assert not profile.url_endpoint.endswith("?wsdl")


def test_tribunal_sem_endpoint_confirmado_nao_tem_perfil():
    """Nao confirmados no probe de 2026-07-22 (WAF 403 ou host ausente).
    403 nao prova ausencia de MNI — prova ausencia de confirmacao, e sem
    confirmacao a rota tem de cair no agente local."""
    for tribunal in ("TJMG", "TJDFT", "TJBA", "TRT3", "TRT15"):
        assert resolve_mni_profile(tribunal, "1") is None, tribunal
