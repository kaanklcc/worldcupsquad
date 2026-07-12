import { NextResponse } from 'next/server';

interface CCTPRequest {
  walletAddress: string;
  amount: number;
  sourceChain: string;
}

export async function POST(request: Request) {
  try {
    const body: CCTPRequest = await request.json();
    const { walletAddress, amount, sourceChain } = body;

    if (!walletAddress || walletAddress.trim() === '') {
      return NextResponse.json(
        { success: false, message: 'Wallet address is required.' },
        { status: 400 }
      );
    }

    if (amount !== 20) {
      return NextResponse.json(
        { success: false, message: 'Amount must be exactly 20 USDC.' },
        { status: 400 }
      );
    }

    if (!sourceChain || sourceChain.trim() === '') {
      return NextResponse.json(
        { success: false, message: 'Source chain is required.' },
        { status: 400 }
      );
    }

    return NextResponse.json({
      success: true,
      newBudgetBonus: 20,
      txHash: `inj1...simulated_cctp_tx_${Date.now()}`,
      message: `CCTP bridge successful. 20 USDC bridged from ${sourceChain} to Injective. Budget increased by 20M.`,
    });
  } catch {
    return NextResponse.json(
      { success: false, message: 'Invalid request body.' },
      { status: 400 }
    );
  }
}
