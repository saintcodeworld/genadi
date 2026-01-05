import * as anchor from "@coral-xyz/anchor";
import { Program, AnchorProvider, Wallet } from "@coral-xyz/anchor";
import { Connection, Keypair, PublicKey, SystemProgram } from "@solana/web3.js";
import axios, { AxiosError } from "axios";
import * as fs from "fs";
import * as path from "path";
import * as dotenv from "dotenv";

dotenv.config();

interface MarketCapData {
  marketCap: number;
  timestamp: number;
  price: number;
  volume24h: number;
  source: "dexscreener" | "birdeye";
}

interface MarketAccount {
  publicKey: PublicKey;
  account: {
    creator: PublicKey;
    oracleAuthority: PublicKey;
    tokenMint: PublicKey;
    totalYesPool: anchor.BN;
    totalNoPool: anchor.BN;
    targetMarketCap: anchor.BN;
    deadline: anchor.BN;
    isResolved: boolean;
    winner: boolean | null;
    targetReached: boolean;
    resolvedAt: anchor.BN;
    bump: number;
  };
}

class ResolutionBot {
  private connection: Connection;
  private provider: AnchorProvider;
  private program: Program<any>;
  private oracleKeypair: Keypair;
  private checkIntervalMs: number;
  private maxRetries: number;
  private retryDelayMs: number;
  private isRunning: boolean;

  constructor() {
    const rpcUrl = process.env.RPC_URL || "https://api.devnet.solana.com";
    const programId = new PublicKey(process.env.PROGRAM_ID!);
    const oracleKeypairPath = process.env.ORACLE_KEYPAIR_PATH || "./oracle-keypair.json";
    const idlPath = process.env.IDL_PATH || "../target/idl/mememarket.json";

    this.connection = new Connection(rpcUrl, "confirmed");
    this.oracleKeypair = Keypair.fromSecretKey(
      Uint8Array.from(JSON.parse(fs.readFileSync(oracleKeypairPath, "utf-8")))
    );

    const wallet = new Wallet(this.oracleKeypair);
    this.provider = new AnchorProvider(this.connection, wallet, {
      commitment: "confirmed",
    });

    const idl = JSON.parse(fs.readFileSync(idlPath, "utf-8"));
    // Anchor 0.30.1 uses the programId from the IDL, not as a constructor parameter
    this.program = new Program(idl, this.provider);

    this.checkIntervalMs = parseInt(process.env.CHECK_INTERVAL_MS || "60000");
    this.maxRetries = parseInt(process.env.MAX_RETRIES || "3");
    this.retryDelayMs = parseInt(process.env.RETRY_DELAY_MS || "5000");
    this.isRunning = false;

    console.log("================================================================================");
    console.log("PARIMUTUEL MARKET RESOLUTION BOT");
    console.log("================================================================================");
    console.log("DEBUG: Bot initialized");
    console.log("DEBUG: Oracle Authority:", this.oracleKeypair.publicKey.toString());
    console.log("DEBUG: Program ID:", programId.toString());
    console.log("DEBUG: RPC URL:", rpcUrl);
    console.log("DEBUG: Check Interval:", this.checkIntervalMs / 1000, "seconds");
    console.log("================================================================================\n");
  }

  async start() {
    this.isRunning = true;
    console.log("🚀 Starting market resolution bot...\n");

    await this.checkOracleBalance();

    while (this.isRunning) {
      try {
        await this.processMarkets();
      } catch (error) {
        console.error("ERROR: Error in main loop:", error);
      }

      console.log(`\n⏰ Waiting ${this.checkIntervalMs / 1000} seconds until next check...\n`);
      await this.sleep(this.checkIntervalMs);
    }
  }

  stop() {
    console.log("\n🛑 Stopping resolution bot...");
    this.isRunning = false;
  }

  private async checkOracleBalance() {
    const balance = await this.connection.getBalance(this.oracleKeypair.publicKey);
    const balanceSOL = balance / 1e9;

    console.log("💰 Oracle Wallet Balance:", balanceSOL.toFixed(4), "SOL");

    if (balanceSOL < 0.01) {
      console.warn("⚠️  WARNING: Oracle balance is low! Please fund the wallet.");
      console.warn(`    Address: ${this.oracleKeypair.publicKey.toString()}`);
    }
    console.log();
  }

  private async processMarkets() {
    console.log("🔍 Fetching active markets...");

    const markets = await this.fetchActiveMarkets();
    console.log(`DEBUG: Found ${markets.length} active market(s)\n`);

    if (markets.length === 0) {
      console.log("✅ No active markets to process");
      return;
    }

    for (const market of markets) {
      try {
        await this.processMarket(market);
      } catch (error) {
        console.error(`ERROR: Failed to process market ${market.publicKey.toString()}:`, error);
      }
    }
  }

  private async fetchActiveMarkets(): Promise<MarketAccount[]> {
    try {
      const allMarkets = await (this.program.account as any).market.all();

      const activeMarkets = allMarkets.filter((market: any) => {
        return !market.account.isResolved;
      });

      return activeMarkets as MarketAccount[];
    } catch (error) {
      console.error("ERROR: Failed to fetch markets:", error);
      return [];
    }
  }

  private async processMarket(market: MarketAccount) {
    const marketPubkey = market.publicKey.toString();
    const tokenMint = market.account.tokenMint.toString();
    const targetMarketCap = market.account.targetMarketCap.toNumber();
    const deadline = market.account.deadline.toNumber();
    const currentTime = Math.floor(Date.now() / 1000);

    console.log("─────────────────────────────────────────────────────────────────────────────");
    console.log(`📊 Processing Market: ${marketPubkey.substring(0, 8)}...`);
    console.log(`   Token: ${tokenMint}`);
    console.log(`   Target: $${(targetMarketCap / 1_000_000).toLocaleString()}`);
    console.log(`   Deadline: ${new Date(deadline * 1000).toISOString()}`);

    const timeUntilDeadline = deadline - currentTime;
    if (timeUntilDeadline > 0) {
      const hours = Math.floor(timeUntilDeadline / 3600);
      const minutes = Math.floor((timeUntilDeadline % 3600) / 60);
      console.log(`   Time Remaining: ${hours}h ${minutes}m`);
    } else {
      console.log(`   Time Remaining: EXPIRED (${Math.abs(timeUntilDeadline)}s ago)`);
    }

    const marketCapData = await this.fetchMarketCapWithRetry(tokenMint);

    if (!marketCapData) {
      console.log("⚠️  WARNING: Could not fetch market cap data - skipping market");
      return;
    }

    const currentMarketCap = marketCapData.marketCap;
    console.log(`   Current Market Cap: $${currentMarketCap.toLocaleString()}`);
    console.log(`   Data Source: ${marketCapData.source}`);
    console.log(`   Data Age: ${currentTime - marketCapData.timestamp}s`);

    const dataAge = currentTime - marketCapData.timestamp;
    if (dataAge > 300) {
      console.log("⚠️  WARNING: Market cap data is stale (>5 minutes) - skipping resolution");
      return;
    }

    const targetReached = currentMarketCap >= targetMarketCap / 1_000_000;
    const deadlinePassed = currentTime >= deadline;

    console.log(`   Target Reached: ${targetReached ? "✅ YES" : "❌ NO"}`);
    console.log(`   Deadline Passed: ${deadlinePassed ? "✅ YES" : "❌ NO"}`);

    if (targetReached) {
      console.log("\n🎯 CONDITION MET: Target reached - Resolving market as YES");
      await this.resolveMarket(market, currentMarketCap, marketCapData.timestamp, true);
    } else if (deadlinePassed) {
      console.log("\n⏰ CONDITION MET: Deadline passed without target - Resolving market as NO");
      await this.resolveMarket(market, currentMarketCap, marketCapData.timestamp, false);
    } else {
      console.log("\n⏳ No resolution conditions met yet - waiting...");
    }
  }

  private async fetchMarketCapWithRetry(tokenMint: string): Promise<MarketCapData | null> {
    for (let attempt = 1; attempt <= this.maxRetries; attempt++) {
      try {
        console.log(`   Fetching market cap (attempt ${attempt}/${this.maxRetries})...`);

        const data = await this.fetchMarketCapFromDexScreener(tokenMint);
        if (data) {
          return data;
        }

        const birdeyeApiKey = process.env.BIRDEYE_API_KEY;
        if (birdeyeApiKey) {
          console.log("   Trying Birdeye API as fallback...");
          const birdeyeData = await this.fetchMarketCapFromBirdeye(tokenMint, birdeyeApiKey);
          if (birdeyeData) {
            return birdeyeData;
          }
        }

        if (attempt < this.maxRetries) {
          console.log(`   Retry ${attempt} failed, waiting ${this.retryDelayMs / 1000}s...`);
          await this.sleep(this.retryDelayMs);
        }
      } catch (error) {
        console.error(`   ERROR on attempt ${attempt}:`, error instanceof Error ? error.message : error);
        if (attempt < this.maxRetries) {
          await this.sleep(this.retryDelayMs);
        }
      }
    }

    console.error("   ERROR: All retry attempts exhausted");
    return null;
  }

  private async fetchMarketCapFromDexScreener(tokenMint: string): Promise<MarketCapData | null> {
    try {
      const response = await axios.get(
        `https://api.dexscreener.com/latest/dex/tokens/${tokenMint}`,
        { timeout: 10000 }
      );

      if (response.data?.pairs && response.data.pairs.length > 0) {
        const pair = response.data.pairs[0];
        const marketCap = parseFloat(pair.fdv || pair.marketCap || "0");
        const price = parseFloat(pair.priceUsd || "0");
        const volume24h = parseFloat(pair.volume?.h24 || "0");

        if (marketCap > 0) {
          return {
            marketCap,
            timestamp: Math.floor(Date.now() / 1000),
            price,
            volume24h,
            source: "dexscreener",
          };
        }
      }

      return null;
    } catch (error) {
      if (axios.isAxiosError(error)) {
        console.error(`   DexScreener API error: ${error.message}`);
      }
      return null;
    }
  }

  private async fetchMarketCapFromBirdeye(
    tokenMint: string,
    apiKey: string
  ): Promise<MarketCapData | null> {
    try {
      const response = await axios.get(
        `https://public-api.birdeye.so/defi/token_overview?address=${tokenMint}`,
        {
          headers: { "X-API-KEY": apiKey },
          timeout: 10000,
        }
      );

      if (response.data?.data) {
        const data = response.data.data;
        const marketCap = parseFloat(data.mc || "0");
        const price = parseFloat(data.price || "0");
        const volume24h = parseFloat(data.v24hUSD || "0");

        if (marketCap > 0) {
          return {
            marketCap,
            timestamp: Math.floor(Date.now() / 1000),
            price,
            volume24h,
            source: "birdeye",
          };
        }
      }

      return null;
    } catch (error) {
      if (axios.isAxiosError(error)) {
        console.error(`   Birdeye API error: ${error.message}`);
      }
      return null;
    }
  }

  private async resolveMarket(
    market: MarketAccount,
    currentMarketCap: number,
    timestamp: number,
    winner: boolean
  ) {
    try {
      console.log("\n📝 Preparing resolution transaction...");
      console.log(`   Winner: ${winner ? "YES" : "NO"}`);
      console.log(`   Market Cap: $${currentMarketCap.toLocaleString()}`);
      console.log(`   Timestamp: ${timestamp}`);

      const marketCapWithDecimals = Math.floor(currentMarketCap * 1_000_000);

      const [marketPda] = PublicKey.findProgramAddressSync(
        [Buffer.from("market"), market.publicKey.toBuffer()],
        this.program.programId
      );

      const verifyAuthority = market.account.oracleAuthority.toString();
      const botAuthority = this.oracleKeypair.publicKey.toString();

      console.log(`   Verifying oracle authority...`);
      console.log(`   Expected: ${verifyAuthority}`);
      console.log(`   Bot Key:  ${botAuthority}`);

      if (verifyAuthority !== botAuthority) {
        console.error("❌ ERROR: Oracle authority mismatch!");
        console.error("   This bot is not authorized to resolve this market.");
        return;
      }

      console.log("   ✅ Authority verified");

      console.log("\n🔄 Sending resolution transaction...");

      const tx = await (this.program.methods as any)
        .parimutuelResolveMarket(
          "",
          new anchor.BN(marketCapWithDecimals),
          new anchor.BN(timestamp)
        )
        .accounts({
          market: market.publicKey,
          oracle: this.oracleKeypair.publicKey,
        })
        .signers([this.oracleKeypair])
        .rpc();

      console.log("✅ Market resolved successfully!");
      console.log(`   Transaction: ${tx}`);
      console.log(`   Explorer: https://solscan.io/tx/${tx}?cluster=devnet`);

      const updatedMarket = await (this.program.account as any).market.fetch(market.publicKey);
      console.log("\n📊 Market Status:");
      console.log(`   Resolved: ${updatedMarket.isResolved}`);
      console.log(`   Winner: ${updatedMarket.winner ? "YES" : "NO"}`);
      console.log(`   Target Reached: ${updatedMarket.targetReached}`);
      console.log(`   Total YES Pool: ${updatedMarket.totalYesPool.toNumber() / 1e9} SOL`);
      console.log(`   Total NO Pool: ${updatedMarket.totalNoPool.toNumber() / 1e9} SOL`);
    } catch (error: any) {
      console.error("❌ ERROR: Failed to resolve market");

      if (error.logs) {
        console.error("\n📋 Transaction Logs:");
        error.logs.forEach((log: string) => console.error(`   ${log}`));
      }

      if (error.message) {
        console.error(`\n💬 Error Message: ${error.message}`);
      }

      if (error.message?.includes("Unauthorized")) {
        console.error("\n⚠️  This oracle is not authorized to resolve this market");
      } else if (error.message?.includes("MarketAlreadyResolved")) {
        console.error("\n⚠️  Market has already been resolved");
      } else if (error.message?.includes("StaleData")) {
        console.error("\n⚠️  Market cap data is too old (>5 minutes)");
      } else if (error.message?.includes("CannotResolveYet")) {
        console.error("\n⚠️  Resolution conditions not met yet");
      }
    }
  }

  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}

async function main() {
  const requiredEnvVars = ["PROGRAM_ID", "ORACLE_KEYPAIR_PATH"];
  const missing = requiredEnvVars.filter((v) => !process.env[v]);

  if (missing.length > 0) {
    console.error("❌ ERROR: Missing required environment variables:");
    missing.forEach((v) => console.error(`   - ${v}`));
    console.error("\nPlease check your .env file");
    process.exit(1);
  }

  const bot = new ResolutionBot();

  process.on("SIGINT", () => {
    bot.stop();
    process.exit(0);
  });

  process.on("SIGTERM", () => {
    bot.stop();
    process.exit(0);
  });

  try {
    await bot.start();
  } catch (error) {
    console.error("❌ FATAL ERROR:", error);
    process.exit(1);
  }
}

main();
