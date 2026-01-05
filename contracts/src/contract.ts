import { 
  Connection, 
  PublicKey, 
  SystemProgram,
  LAMPORTS_PER_SOL
} from '@solana/web3.js';
import { 
  AnchorProvider, 
  Program, 
  Wallet, 
  setProvider,
  BN 
} from '@project-serum/anchor';
import { MemeMarket } from '../target/types/mememarket';

// Debug: Program ID from lib.rs - update after deployment
const PROGRAM_ID = new PublicKey('5rw87nNYE9Ep7zv6Yv8adK86fP8MSSYRAMq276C8Dbkq');

// Debug: Treasury wallet that receives 0.015 SOL market creation fee
const TREASURY_WALLET = new PublicKey('GXEJmMfgtnqNpHzbk5moMFiMXMNB7GagjAVvTv1tZi3g');

// Debug: Market creation fee in lamports (0.015 SOL)
const MARKET_CREATION_FEE = 0.015 * LAMPORTS_PER_SOL;

/**
 * MemeMarket Parimutuel Contract Client
 * Debug: Handles all interactions with the on-chain parimutuel betting program
 */
export class MemeMarketContract {
  private connection: Connection;
  private program: Program<MemeMarket>;
  private provider: AnchorProvider;
  private wallet: Wallet;

  constructor(connection: Connection, wallet: Wallet, programId?: PublicKey) {
    this.connection = connection;
    this.wallet = wallet;
    this.provider = new AnchorProvider(connection, wallet, {
      commitment: 'confirmed',
      preflightCommitment: 'confirmed',
    });
    setProvider(this.provider);
    
    // Debug: Initialize program with IDL - update path after build
    const idl = require('../target/idl/mememarket.json');
    this.program = new Program<MemeMarket>(
      idl,
      programId || PROGRAM_ID,
      this.provider
    );
    
    console.log('DEBUG: MemeMarketContract initialized');
    console.log('DEBUG: Program ID:', this.program.programId.toBase58());
  }

  /**
   * Derive market PDA from seed
   * Debug: Markets are identified by a unique seed string
   */
  async getMarketPDA(marketSeed: string): Promise<[PublicKey, number]> {
    return PublicKey.findProgramAddressSync(
      [Buffer.from('market'), Buffer.from(marketSeed)],
      this.program.programId
    );
  }

  /**
   * Derive user bet PDA for a specific market
   * Debug: Each user has one bet account per market
   */
  async getUserBetPDA(marketPubkey: PublicKey, userPubkey: PublicKey): Promise<[PublicKey, number]> {
    return PublicKey.findProgramAddressSync(
      [Buffer.from('user_bet'), marketPubkey.toBuffer(), userPubkey.toBuffer()],
      this.program.programId
    );
  }

  /**
   * Derive escrow PDA for a market
   * Debug: Escrow holds all bet funds until market resolution
   */
  async getEscrowPDA(marketPubkey: PublicKey): Promise<[PublicKey, number]> {
    return PublicKey.findProgramAddressSync(
      [Buffer.from('escrow'), marketPubkey.toBuffer()],
      this.program.programId
    );
  }

  /**
   * Initialize a new parimutuel market (permissionless)
   * Debug: Charges 0.015 SOL fee to treasury wallet
   * @param marketSeed - Unique seed string for the market PDA
   * @param oracleAuthority - Oracle pubkey that can resolve the market
   * @param tokenMint - Token to track market cap for
   * @param targetMarketCap - Target market cap in USD with 6 decimals (e.g., 1_000_000_000000 = $1M)
   * @param deadline - Unix timestamp when betting closes
   * @param treasuryWallet - Wallet to receive the 0.015 SOL creation fee
   */
  async initializeMarket(
    marketSeed: string,
    oracleAuthority: PublicKey,
    tokenMint: PublicKey,
    targetMarketCap: number,
    deadline: number,
    treasuryWallet: PublicKey = TREASURY_WALLET
  ): Promise<string> {
    console.log('DEBUG: Initializing market with seed:', marketSeed);
    console.log('DEBUG: Target market cap:', targetMarketCap);
    console.log('DEBUG: Deadline:', new Date(deadline * 1000).toISOString());
    console.log('DEBUG: Treasury will receive 0.015 SOL fee');
    
    try {
      const [marketPDA] = await this.getMarketPDA(marketSeed);
      console.log('DEBUG: Market PDA:', marketPDA.toBase58());
      
      const tx = await this.program.methods
        .parimutuelInitializeMarket(
          marketSeed,
          oracleAuthority,
          tokenMint,
          new BN(targetMarketCap),
          new BN(deadline)
        )
        .accounts({
          market: marketPDA,
          treasury: treasuryWallet,
          creator: this.wallet.publicKey,
          systemProgram: SystemProgram.programId,
        })
        .rpc();

      console.log('DEBUG: Market initialized with transaction:', tx);
      return tx;
    } catch (error) {
      console.error('DEBUG: Error initializing market:', error);
      throw error;
    }
  }

  /**
   * Place a bet on YES or NO
   * Debug: Transfers SOL from user to market escrow PDA
   * @param marketSeed - Market seed string
   * @param amount - Amount in lamports to bet
   * @param side - true = YES, false = NO
   */
  async placeBet(
    marketSeed: string,
    amount: number,
    side: boolean
  ): Promise<string> {
    console.log('DEBUG: Placing bet on', side ? 'YES' : 'NO');
    console.log('DEBUG: Amount:', amount / LAMPORTS_PER_SOL, 'SOL');
    
    try {
      const [marketPDA] = await this.getMarketPDA(marketSeed);
      const [userBetPDA] = await this.getUserBetPDA(marketPDA, this.wallet.publicKey);
      const [escrowPDA] = await this.getEscrowPDA(marketPDA);
      
      console.log('DEBUG: Market PDA:', marketPDA.toBase58());
      console.log('DEBUG: User bet PDA:', userBetPDA.toBase58());
      console.log('DEBUG: Escrow PDA:', escrowPDA.toBase58());
      
      const tx = await this.program.methods
        .parimutuelPlaceBet(
          marketSeed,
          new BN(amount),
          side
        )
        .accounts({
          market: marketPDA,
          userBet: userBetPDA,
          escrow: escrowPDA,
          user: this.wallet.publicKey,
          systemProgram: SystemProgram.programId,
        })
        .rpc();

      console.log('DEBUG: Bet placed with transaction:', tx);
      return tx;
    } catch (error) {
      console.error('DEBUG: Error placing bet:', error);
      throw error;
    }
  }

  /**
   * Resolve market with oracle data (oracle only)
   * Debug: Oracle provides current market cap and timestamp
   * @param marketSeed - Market seed string
   * @param currentMarketCap - Current market cap from oracle in USD with 6 decimals
   * @param timestamp - Oracle timestamp for verification
   */
  async resolveMarket(
    marketSeed: string,
    currentMarketCap: number,
    timestamp: number
  ): Promise<string> {
    console.log('DEBUG: Resolving market with seed:', marketSeed);
    console.log('DEBUG: Current market cap:', currentMarketCap);
    console.log('DEBUG: Oracle timestamp:', timestamp);
    
    try {
      const [marketPDA] = await this.getMarketPDA(marketSeed);
      
      const tx = await this.program.methods
        .parimutuelResolveMarket(
          marketSeed,
          new BN(currentMarketCap),
          new BN(timestamp)
        )
        .accounts({
          market: marketPDA,
          oracle: this.wallet.publicKey,
        })
        .rpc();

      console.log('DEBUG: Market resolved with transaction:', tx);
      return tx;
    } catch (error) {
      console.error('DEBUG: Error resolving market:', error);
      throw error;
    }
  }

  /**
   * Claim reward after market resolution
   * Debug: Calculates proportional payout from total pool
   * @param marketSeed - Market seed string
   */
  async claimReward(marketSeed: string): Promise<string> {
    console.log('DEBUG: Claiming reward for market:', marketSeed);
    
    try {
      const [marketPDA] = await this.getMarketPDA(marketSeed);
      const [userBetPDA] = await this.getUserBetPDA(marketPDA, this.wallet.publicKey);
      const [escrowPDA] = await this.getEscrowPDA(marketPDA);
      
      const tx = await this.program.methods
        .parimutuelClaimReward(marketSeed)
        .accounts({
          market: marketPDA,
          userBet: userBetPDA,
          escrow: escrowPDA,
          user: this.wallet.publicKey,
          systemProgram: SystemProgram.programId,
        })
        .rpc();

      console.log('DEBUG: Reward claimed with transaction:', tx);
      return tx;
    } catch (error) {
      console.error('DEBUG: Error claiming reward:', error);
      throw error;
    }
  }

  /**
   * Get market information
   * Debug: Fetches on-chain market account data
   */
  async getMarketInfo(marketSeed: string) {
    try {
      const [marketPDA] = await this.getMarketPDA(marketSeed);
      const marketAccount = await this.program.account.market.fetch(marketPDA);
      
      console.log('DEBUG: Market info fetched');
      console.log('DEBUG: Total YES pool:', Number(marketAccount.totalYesPool) / LAMPORTS_PER_SOL, 'SOL');
      console.log('DEBUG: Total NO pool:', Number(marketAccount.totalNoPool) / LAMPORTS_PER_SOL, 'SOL');
      console.log('DEBUG: Is resolved:', marketAccount.isResolved);
      
      return {
        creator: marketAccount.creator,
        oracleAuthority: marketAccount.oracleAuthority,
        tokenMint: marketAccount.tokenMint,
        totalYesPool: Number(marketAccount.totalYesPool),
        totalNoPool: Number(marketAccount.totalNoPool),
        targetMarketCap: Number(marketAccount.targetMarketCap),
        deadline: Number(marketAccount.deadline),
        isResolved: marketAccount.isResolved,
        winner: marketAccount.winner,
        targetReached: marketAccount.targetReached,
        resolvedAt: Number(marketAccount.resolvedAt),
      };
    } catch (error) {
      console.error('DEBUG: Error fetching market info:', error);
      throw error;
    }
  }

  /**
   * Get user's bet info for a specific market
   * Debug: Returns user's bet amount, side, and claim status
   */
  async getUserBetInfo(marketSeed: string, userPubkey?: PublicKey) {
    try {
      const user = userPubkey || this.wallet.publicKey;
      const [marketPDA] = await this.getMarketPDA(marketSeed);
      const [userBetPDA] = await this.getUserBetPDA(marketPDA, user);
      
      const userBetAccount = await this.program.account.userBet.fetch(userBetPDA);
      
      console.log('DEBUG: User bet info fetched');
      console.log('DEBUG: Amount:', Number(userBetAccount.amount) / LAMPORTS_PER_SOL, 'SOL');
      console.log('DEBUG: Side:', userBetAccount.side ? 'YES' : 'NO');
      console.log('DEBUG: Claimed:', userBetAccount.claimed);
      
      return {
        user: userBetAccount.user,
        market: userBetAccount.market,
        amount: Number(userBetAccount.amount),
        side: userBetAccount.side,
        claimed: userBetAccount.claimed,
      };
    } catch (error) {
      console.error('DEBUG: Error fetching user bet info:', error);
      return null;
    }
  }

  /**
   * Calculate implied probability from pool sizes
   * Debug: YES probability = YES pool / (YES pool + NO pool)
   */
  calculateImpliedProbability(yesPool: number, noPool: number): { yes: number; no: number } {
    const total = yesPool + noPool;
    if (total === 0) {
      return { yes: 0.5, no: 0.5 };
    }
    return {
      yes: yesPool / total,
      no: noPool / total,
    };
  }

  /**
   * Calculate potential payout for a bet
   * Debug: Payout = (bet amount / winning pool) * total pool
   */
  calculatePotentialPayout(
    betAmount: number,
    side: boolean,
    currentYesPool: number,
    currentNoPool: number
  ): number {
    const newYesPool = side ? currentYesPool + betAmount : currentYesPool;
    const newNoPool = side ? currentNoPool : currentNoPool + betAmount;
    const winningPool = side ? newYesPool : newNoPool;
    const totalPool = newYesPool + newNoPool;
    
    return (betAmount / winningPool) * totalPool;
  }

  /**
   * Get wallet SOL balance
   */
  async getBalance(): Promise<number> {
    const balance = await this.connection.getBalance(this.wallet.publicKey);
    return balance;
  }
}
