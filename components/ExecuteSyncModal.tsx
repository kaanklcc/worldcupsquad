'use client';

import { useEffect, useRef } from 'react';

export type SyncStage = 'signing' | 'broadcasting' | 'success' | 'error';

interface ExecuteSyncModalProps {
  isOpen: boolean;
  stage: SyncStage;
  txHash?: string;
  error?: string;
  onClose: () => void;
}

interface ConfettiParticle {
  x: number;
  y: number;
  color: string;
  size: number;
  speedX: number;
  speedY: number;
  rotation: number;
  rotationSpeed: number;
}

export default function ExecuteSyncModal({
  isOpen,
  stage,
  txHash,
  error,
  onClose,
}: ExecuteSyncModalProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number | null>(null);

  useEffect(() => {
    if (stage !== 'success' || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    canvas.width = canvas.parentElement?.clientWidth || 500;
    canvas.height = canvas.parentElement?.clientHeight || 400;

    const colors = ['#dfb53b', '#2ecc71', '#3498db', '#e74c3c', '#9b59b6', '#ffffff'];
    const particles: ConfettiParticle[] = [];

    for (let i = 0; i < 120; i++) {
      particles.push({
        x: canvas.width / 2,
        y: canvas.height / 2 + 50,
        color: colors[Math.floor(Math.random() * colors.length)],
        size: Math.random() * 8 + 4,
        speedX: (Math.random() - 0.5) * 12,
        speedY: (Math.random() - 0.7) * 16 - 4,
        rotation: Math.random() * 360,
        rotationSpeed: (Math.random() - 0.5) * 10,
      });
    }

    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      let activeParticles = 0;

      particles.forEach((particle) => {
        particle.x += particle.speedX;
        particle.y += particle.speedY;
        particle.speedY += 0.25;
        particle.speedX *= 0.98;
        particle.rotation += particle.rotationSpeed;

        if (particle.y < canvas.height + 20) {
          activeParticles++;
          ctx.save();
          ctx.translate(particle.x, particle.y);
          ctx.rotate((particle.rotation * Math.PI) / 180);
          ctx.fillStyle = particle.color;
          ctx.fillRect(-particle.size / 2, -particle.size / 2, particle.size, particle.size);
          ctx.restore();
        }
      });

      if (activeParticles > 0) {
        animationRef.current = requestAnimationFrame(animate);
      }
    };

    animate();

    return () => {
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
    };
  }, [stage]);

  if (!isOpen) return null;

  const isFinished = stage === 'success' || stage === 'error';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/75 backdrop-blur-md"
        onClick={isFinished ? onClose : undefined}
      />

      <div className="relative bg-slate-950 border border-slate-800 rounded-2xl shadow-2xl w-full max-w-md p-6 overflow-hidden flex flex-col items-center justify-center min-h-[340px] text-center z-10">
        {stage === 'success' && (
          <canvas ref={canvasRef} className="absolute inset-0 w-full h-full pointer-events-none z-0" />
        )}

        {stage === 'signing' && (
          <div className="flex flex-col items-center gap-4 animate-fade-in z-10">
            <div className="h-16 w-16 rounded-full border-4 border-slate-800 border-t-amber-400 animate-spin flex items-center justify-center">
              <span className="material-symbols-outlined text-amber-400 text-3xl">key</span>
            </div>
            <h3 className="font-display-lg text-xl uppercase tracking-wider text-slate-100 mt-2">Validating Squad</h3>
            <p className="font-mono-jb text-xs text-slate-400 max-w-xs">
              Checking the squad snapshot and manager authorization...
            </p>
          </div>
        )}

        {stage === 'broadcasting' && (
          <div className="flex flex-col items-center gap-4 animate-fade-in z-10">
            <div className="h-16 w-16 rounded-full border-4 border-slate-800 border-t-emerald-500 animate-spin flex items-center justify-center">
              <span className="material-symbols-outlined text-emerald-500 text-3xl animate-pulse">network_check</span>
            </div>
            <h3 className="font-display-lg text-xl uppercase tracking-wider text-slate-100 mt-2">Broadcasting Changes</h3>
            <p className="font-mono-jb text-xs text-slate-400 max-w-xs">
              Persisting your squad state through the Auto-Gaffer API...
            </p>
          </div>
        )}

        {stage === 'success' && (
          <div className="flex flex-col items-center gap-4 animate-fade-in z-10">
            <div className="h-16 w-16 rounded-full bg-emerald-500/20 border-2 border-emerald-500 flex items-center justify-center drop-shadow-[0_0_15px_rgba(46,204,113,0.5)]">
              <span className="material-symbols-outlined text-emerald-500 text-4xl font-bold">check</span>
            </div>
            <h3 className="font-display-lg text-2xl uppercase tracking-wider text-slate-100 mt-2">Sync Successful!</h3>
            <p className="font-body-md text-xs text-slate-300 max-w-xs px-2">
              Your World Cup tactics and squad lineups have been saved.
            </p>
            <div className="w-full bg-slate-900 border border-slate-800 p-2.5 rounded font-mono-jb text-[10px] text-slate-400 text-left mb-2">
              <div className="text-emerald-400 font-bold uppercase mb-1">Receipt details:</div>
              <div>Status: CONFIRMED</div>
              <div className="truncate">Tx: {txHash || 'squad_snapshot_saved'}</div>
            </div>
            <button onClick={onClose} className="gold-gradient font-display-lg text-xs uppercase px-8 py-2 rounded-sm shadow-md hover:brightness-110 transition-all font-bold">
              Done
            </button>
          </div>
        )}

        {stage === 'error' && (
          <div className="flex flex-col items-center gap-4 animate-fade-in z-10">
            <div className="h-16 w-16 rounded-full bg-red-500/20 border-2 border-red-500 flex items-center justify-center">
              <span className="material-symbols-outlined text-red-400 text-4xl">error</span>
            </div>
            <h3 className="font-display-lg text-2xl uppercase tracking-wider text-slate-100 mt-2">Sync Failed</h3>
            <p className="font-body-md text-xs text-red-300 max-w-xs px-2">{error || 'The squad could not be saved.'}</p>
            <button onClick={onClose} className="bg-slate-800 text-slate-100 font-display-lg text-xs uppercase px-8 py-2 rounded-sm shadow-md hover:bg-slate-700 transition-all font-bold">
              Close
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
