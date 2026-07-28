"use client";

import { AlertTriangle, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { listarOabsMonitoradas, OabMonitorada, removerOabMonitorada } from "@/lib/api";
import { humanError } from "@/lib/errors";
import type { Settings } from "@/lib/settings";
import UfSearchSelect from "../UfSearchSelect";
import { useToast } from "../Toast";
import { AsyncState, LoadingButton, Modal, Skeleton } from "../ui";

// OAB padrão dos formulários de captura + as OABs que já geraram dados.
// Remover uma OAB apaga o que ela capturou, então passa por confirmação.
export default function CaptureTab({
  settings,
  offline,
  onUpdate,
  onOabChanged
}: {
  settings: Settings;
  offline: boolean;
  onUpdate: (patch: Partial<Settings>) => void;
  onOabChanged: () => Promise<void>;
}) {
  const toast = useToast();
  const [oabs, setOabs] = useState<OabMonitorada[]>([]);
  const [loading, setLoading] = useState(true);
  const [retrying, setRetrying] = useState(false);
  const [removingId, setRemovingId] = useState<number | null>(null);
  const [toRemove, setToRemove] = useState<OabMonitorada | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (offline) {
      setOabs([]);
      setLoading(false);
      return;
    }
    try {
      setOabs(await listarOabsMonitoradas());
      setError(null);
    } catch (err) {
      setError(humanError(err, "Não foi possível carregar as OABs monitoradas"));
    } finally {
      setLoading(false);
    }
  }, [offline]);

  useEffect(() => {
    void load();
  }, [load]);

  async function remove(oab: OabMonitorada) {
    setRemovingId(oab.id);
    try {
      await removerOabMonitorada(oab.id, true);
      await load();
      await onOabChanged();
      setError(null);
      setToRemove(null);
      toast({
        kind: "success",
        title: `OAB ${oab.oab}/${oab.uf} removida`,
        description: "Dados capturados por ela foram apagados."
      });
    } catch (err) {
      setError(humanError(err, "A OAB não foi removida"));
    } finally {
      setRemovingId(null);
    }
  }

  return (
    <>
      <section className="settingsSection">
        <div className="settingsSectionHead">
          <h4>Padrões de captura</h4>
          <p>Preenchidos automaticamente ao iniciar uma nova captura.</p>
        </div>
        <div className="settingsRow ufRow">
          <label>
            OAB padrão
            <input
              value={settings.defaultOab}
              placeholder="Número da OAB"
              onChange={(e) => onUpdate({ defaultOab: e.target.value })}
            />
          </label>
          <label>
            UF
            <UfSearchSelect
              value={settings.defaultUf}
              disabled={offline}
              name="default_uf"
              onChange={(uf) => onUpdate({ defaultUf: uf })}
            />
          </label>
        </div>
      </section>

      <section className="settingsSection">
        <div className="settingsSectionHead">
          <h4>OABs monitoradas</h4>
          <p>Cada uma alimenta a captura automática de intimações.</p>
        </div>
        <AsyncState
          loading={loading}
          error={error}
          empty={!oabs.length}
          compactError
          skeleton={
            <div className="skeletonGroup" aria-hidden="true">
              <Skeleton height={38} radius={6} />
              <Skeleton height={38} radius={6} />
            </div>
          }
          emptyState={
            <small className="settingsHint">Nenhuma OAB capturada ainda.</small>
          }
          retrying={retrying}
          onRetry={() => {
            setRetrying(true);
            void load().finally(() => setRetrying(false));
          }}
        >
          <div className="modalListRows">
            {oabs.map((oab) => (
              <div className="modalListRow" key={oab.id}>
                <span>
                  {oab.oab}/{oab.uf}
                </span>
                <LoadingButton
                  className="toolbarButton compact danger"
                  disabled={offline}
                  loading={removingId === oab.id}
                  icon={<Trash2 size={14} />}
                  onClick={() => {
                    setError(null);
                    setToRemove(oab);
                  }}
                >
                  Remover dados
                </LoadingButton>
              </div>
            ))}
          </div>
        </AsyncState>
      </section>

      {toRemove ? (
        <Modal
          onClose={() => {
            if (removingId === null) setToRemove(null);
          }}
          labelledBy="removeOabConfirmTitle"
          className="confirmCard"
        >
          <div className="confirmIcon danger" aria-hidden="true">
            <AlertTriangle size={18} />
          </div>
          <div className="confirmBody">
            <span className="settingsLabel" id="removeOabConfirmTitle">
              Remover OAB {toRemove.oab}/{toRemove.uf}?
            </span>
            <p>
              Esta ação apaga intimações, prazos, processos e petições capturados por essa OAB.
              A operação não pode ser desfeita.
            </p>
            {error ? (
              <small className="settingsHint vaultError" role="alert">
                {error}
              </small>
            ) : null}
          </div>
          <div className="modalActions">
            <button
              type="button"
              className="toolbarButton compact"
              disabled={removingId !== null}
              onClick={() => setToRemove(null)}
            >
              Cancelar
            </button>
            <LoadingButton
              className="toolbarButton compact danger confirmDanger"
              loading={removingId === toRemove.id}
              icon={<Trash2 size={14} />}
              onClick={() => void remove(toRemove)}
            >
              Remover definitivamente
            </LoadingButton>
          </div>
        </Modal>
      ) : null}
    </>
  );
}
