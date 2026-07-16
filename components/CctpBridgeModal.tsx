'use client';

import { useState } from 'react';
import { apiFetch } from '@/lib/api';
import { approveAndBurn, connectWalletOnChain, mintAttestedUsdc, type CctpConfig } from '@/lib/cctp';
import type { CCTPReceipt } from '@/types';

type Stage = 'ready' | 'intent' | 'burn' | 'attestation' | 'mint' | 'confirm' | 'success' | 'error';

interface CctpBridgeModalProps {
  isOpen: boolean;
  savedWallet?: string | null;
  onClose: () => void;
  onComplete: (receipt: CCTPReceipt) => void;
}

const stageCopy: Record<Exclude<Stage, 'error' | 'success'>, string> = {
  ready: 'You will sign a real 20 USDC Circle CCTP testnet bridge with your own wallet.',
  intent: 'Creating a replay-safe WCAI bridge intent…',
  burn: 'Approve USDC if needed, then confirm the Sepolia burn in your wallet…',
  attestation: 'Waiting for Circle Iris to attest the confirmed burn…',
  mint: 'Switch to Injective EVM Testnet and confirm the USDC mint…',
  confirm: 'Verifying both on-chain receipts before WCAI updates your budget…',
};

function delay(milliseconds: number) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

export default function CctpBridgeModal({ isOpen, savedWallet, onClose, onComplete }: CctpBridgeModalProps) {
  const [stage, setStage] = useState<Stage>('ready');
  const [error, setError] = useState<string | null>(null);
  const [burnTxHash, setBurnTxHash] = useState<string | null>(null);
  const [mintTxHash, setMintTxHash] = useState<string | null>(null);

  if (!isOpen) return null;

  const close = () => {
    if (!['intent', 'burn', 'attestation', 'mint', 'confirm'].includes(stage)) onClose();
  };

  const startBridge = async () => {
    setError(null);
    setBurnTxHash(null);
    setMintTxHash(null);
    try {
      if (!savedWallet?.startsWith('0x')) throw new Error('Save the same EVM wallet address that you will use in MetaMask before starting CCTP.');
      setStage('intent');
      const intent = await apiFetch<{ operation: { operationId: string }; config: CctpConfig; amount: number }>('/api/cctp/intent', {
        method: 'POST',
        headers: { 'Idempotency-Key': `wcai-cctp-${crypto.randomUUID()}` },
        body: JSON.stringify({ walletAddress: savedWallet, amount: 20, sourceChain: 'Sepolia' }),
      });
      const account = await connectWalletOnChain('sepolia');
      if (account.toLowerCase() !== savedWallet.toLowerCase()) throw new Error('The connected MetaMask account must match the wallet saved in WCAI.');

      setStage('burn');
      const burn = await approveAndBurn(intent.config, account, intent.amount);
      setBurnTxHash(burn);

      setStage('attestation');
      let attestation: { status: string; message?: string; attestation?: string } | null = null;
      for (let attempt = 0; attempt < 60; attempt += 1) {
        const result = await apiFetch<{ status: string; message?: string; attestation?: string }>('/api/cctp/attestation', {
          method: 'POST', body: JSON.stringify({ burnTxHash: burn }),
        });
        if (result.status === 'complete' && result.message && result.attestation) {
          attestation = result;
          break;
        }
        await delay(5000);
      }
      if (!attestation?.message || !attestation.attestation) throw new Error('Circle Iris did not produce an attestation within five minutes. Your burn remains safe; retry the attestation step later.');

      await connectWalletOnChain('injective');
      setStage('mint');
      const mint = await mintAttestedUsdc(intent.config, account, attestation.message as `0x${string}`, attestation.attestation as `0x${string}`);
      setMintTxHash(mint);

      setStage('confirm');
      const receipt = await apiFetch<CCTPReceipt>('/api/cctp/confirm', {
        method: 'POST',
        body: JSON.stringify({ operationId: intent.operation.operationId, walletAddress: savedWallet, amount: 20, burnTxHash: burn, mintTxHash: mint }),
      });
      setStage('success');
      onComplete(receipt);
    } catch (bridgeError) {
      setError(bridgeError instanceof Error ? bridgeError.message : 'CCTP bridge failed.');
      setStage('error');
    }
  };

  const busy = ['intent', 'burn', 'attestation', 'mint', 'confirm'].includes(stage);
  return <div className="fixed inset-0 z-[95] flex items-center justify-center p-4"><button aria-label="Close CCTP bridge" className="absolute inset-0 bg-slate-950/85 backdrop-blur-md" onClick={close} /><section className="relative w-full max-w-xl overflow-hidden rounded-3xl border border-cyan-300/25 bg-slate-950 p-6 text-slate-100 shadow-2xl"><div className="absolute inset-0 pointer-events-none bg-[radial-gradient(circle_at_88%_0%,rgba(6,182,212,.22),transparent_30%),radial-gradient(circle_at_4%_100%,rgba(223,181,59,.15),transparent_30%)]" /><div className="relative"><div className="flex items-start justify-between gap-4"><div><p className="font-mono-jb text-[10px] font-bold uppercase tracking-[.24em] text-cyan-200">Circle CCTP v2 · Testnet</p><h2 className="mt-2 font-display-lg text-3xl uppercase">Acquire 20 USDC backing</h2></div><button onClick={close} disabled={busy} className="rounded-full border border-white/15 p-2 text-slate-300 hover:text-white disabled:opacity-40"><span className="material-symbols-outlined">close</span></button></div><div className="mt-6 rounded-2xl border border-white/10 bg-slate-900/70 p-4"><div className="flex items-center gap-3"><span className={`material-symbols-outlined text-2xl ${stage === 'error' ? 'text-rose-300' : stage === 'success' ? 'text-emerald-300' : 'text-cyan-200'}`}>{stage === 'error' ? 'error' : stage === 'success' ? 'verified' : 'account_balance_wallet'}</span><div><p className="text-sm font-bold">{stage === 'success' ? 'CCTP receipts verified' : stage === 'error' ? 'Bridge was not credited' : 'Manager-signed testnet bridge'}</p><p className="mt-1 text-xs leading-relaxed text-slate-400">{stage === 'success' ? 'The 20M WCAI budget credit was granted only after both receipts were checked.' : stage === 'error' ? error : stageCopy[stage as Exclude<Stage, 'error' | 'success'>]}</p></div></div></div><div className="mt-4 grid gap-2 text-xs text-slate-400 sm:grid-cols-3"><div className="rounded-xl border border-white/10 p-3"><span className="font-bold text-slate-200">1. Burn</span><p className="mt-1">Sepolia USDC</p></div><div className="rounded-xl border border-white/10 p-3"><span className="font-bold text-slate-200">2. Attest</span><p className="mt-1">Circle Iris</p></div><div className="rounded-xl border border-white/10 p-3"><span className="font-bold text-slate-200">3. Mint</span><p className="mt-1">Injective EVM</p></div></div>{burnTxHash && <p className="mt-4 break-all font-mono-jb text-[10px] text-cyan-200">Burn: {burnTxHash}</p>}{mintTxHash && <p className="mt-2 break-all font-mono-jb text-[10px] text-emerald-200">Mint: {mintTxHash}</p>}<div className="mt-6 flex justify-end gap-3">{stage === 'success' || stage === 'error' ? <button onClick={close} className="rounded-lg border border-white/15 px-4 py-2 text-xs font-bold text-slate-200">Close</button> : <button onClick={() => void startBridge()} disabled={busy} className="rounded-lg bg-cyan-300 px-4 py-2 font-display-lg text-xs font-bold uppercase text-slate-950 disabled:opacity-50">{busy ? 'Awaiting wallet / network…' : 'Start real testnet bridge'}</button>}</div></div></section></div>;
}
