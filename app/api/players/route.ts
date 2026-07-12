import { NextResponse } from 'next/server';
import playersData from '@/data/worldcup_players.json';

export async function GET() {
  return NextResponse.json(playersData);
}
