'use client';

import { useEffect, useState, useRef } from 'react';

interface ExecuteSyncModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type SyncStep = 'signing' | 'broadcasting' | 'success';

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

export default function ExecuteSyncModal({ isOpen, onClose }: ExecuteSyncModalProps) {
  const [step, setStep] = useState<SyncStep>('signing');
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number | null>(null);

  // Sync state transitions simulation
  useEffect(() => {
    if (!isOpen) return;

    setStep('signing');
    const t1 = setTimeout(() => {
      setStep('broadcasting');
    }, 1800);

    const t2 = setTimeout(() => {
      setStep('success');
    }, 3600);

    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [isOpen]);

  // Confetti Particle Simulation on Success
  useEffect(() => {
    if (step !== 'success' || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    canvas.width = canvas.parentElement?.clientWidth || 500;
    canvas.height = canvas.parentElement?.clientHeight || 400;

    const colors = ['#dfb53b', '#2ecc71', '#3498db', '#e74c3c', '#9b59b6', '#ffffff'];
    const particles: ConfettiParticle[] = [];

    // Initialize particles
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

      particles.forEach((p) => {
        p.x += p.speedX;
        p.y += p.speedY;
        p.speedY += 0.25; // gravity
        p.speedX *= 0.98; // air resistance
        p.rotation += p.rotationSpeed;

        if (p.y < canvas.height + 20) {
          activeParticles++;
          ctx.save();
          ctx.translate(p.x, p.y);
          ctx.rotate((p.rotation * Math.PI) / 180);
          ctx.fillStyle = p.color;
          ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size);
          ctx.restore();
        }
      });

      if (activeParticles > 0) {
        animationRef.current = requestAnimationFrame(animate);
      }
    };

    animate();

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [step]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/75 backdrop-blur-md" onClick={step === 'success' ? onClose : undefined}></div>

      {/* Modal Card */}
      <div className="relative bg-slate-950 border border-slate-800 rounded-2xl shadow-2xl w-full max-w-md p-6 overflow-hidden flex flex-col items-center justify-center min-h-[340px] text-center z-10">
        
        {/* Canvas for confetti */}
        {step === 'success' && (
          <canvas ref={canvasRef} className="absolute inset-0 w-full h-full pointer-events-none z-0" />
        )}

        {/* Step: Signing */}
        {step === 'signing' && (
          <div className="flex flex-col items-center gap-4 animate-fade-in z-10">
            <div className="h-16 w-16 rounded-full border-4 border-slate-800 border-t-amber-400 animate-spin flex items-center justify-center">
              <span className="material-symbols-outlined text-amber-400 text-3xl">key</span>
            </div>
            <h3 className="font-display-lg text-xl uppercase tracking-wider text-slate-100 mt-2">
              Signing Transaction
            </h3>
            <p className="font-mono-jb text-xs text-slate-400 max-w-xs">
              Wallet: <span className="text-amber-400">inj1x8d...k4m2</span>
              <br />
              Signing payload details on-chain...
            </p>
          </div>
        )}

        {/* Step: Broadcasting */}
        {step === 'broadcasting' && (
          <div className="flex flex-col items-center gap-4 animate-fade-in z-10">
            <div className="h-16 w-16 rounded-full border-4 border-slate-800 border-t-emerald-500 animate-spin flex items-center justify-center">
              <span className="material-symbols-outlined text-emerald-500 text-3xl animate-pulse">network_check</span>
            </div>
            <h3 className="font-display-lg text-xl uppercase tracking-wider text-slate-100 mt-2">
              Broadcasting Changes
            </h3>
            <p className="font-mono-jb text-xs text-slate-400 max-w-xs">
              Submitting new squad and formation state to the Injective Chain testnet...
              <br />
              <span className="text-slate-500">Gas simulated: ~112,000 INJ</span>
            </p>
          </div>
        )}

        {/* Step: Success */}
        {step === 'success' && (
          <div className="flex flex-col items-center gap-4 animate-fade-in z-10">
            <div className="h-16 w-16 rounded-full bg-emerald-500/20 border-2 border-emerald-500 flex items-center justify-center drop-shadow-[0_0_15px_rgba(46,204,113,0.5)]">
              <span className="material-symbols-outlined text-emerald-500 text-4xl font-bold">check</span>
            </div>
            <h3 className="font-display-lg text-2xl uppercase tracking-wider text-slate-100 mt-2">
              Sync Successful!
            </h3>
            <p className="font-body-md text-xs text-slate-300 max-w-xs px-2">
              Your World Cup tactics and squad lineups have been fully registered on Injective.
            </p>
            <div className="w-full bg-slate-900 border border-slate-800 p-2.5 rounded font-mono-jb text-[10px] text-slate-400 text-left mb-2">
              <div className="text-emerald-400 font-bold uppercase mb-1">Receipt details:</div>
              <div>Status: CONFIRMED</div>
              <div className="truncate">Tx: inj_tx_gaffer_sync_{Date.now().toString(16)}</div>
            </div>
            <button
              onClick={onClose}
              className="gold-gradient font-display-lg text-xs uppercase px-8 py-2 rounded-sm shadow-md hover:brightness-110 transition-all font-bold"
            >
              Done
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
