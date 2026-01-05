import * as anchor from "@coral-xyz/anchor";
import { Program, AnchorProvider, Wallet } from "@coral-xyz/anchor";
import { Connection, Keypair, PublicKey } from "@solana/web3.js";
import axios from "axios";
import * as fs from "fs";
import * as path from "path";

interface MarketCapData {
  marketCap: number;
  timestamp: number;
  price: number;
  volume24h: number;
}

interface MarketConfig {
  marketSeed: string;
  tokenMint: string;
  targetMarketCap: number;
  deadline: number;
  checkIntervalMs: number;
}

class MarketCapCrank {
  private connection: Connection;
  private provider: AnchorProvider;
  private program: Program;
  private oracleKeypair: Keypair;
  private markets: Map<string, MarketConfig>;

  constructor(
    rpcUrl: string,
    programId: string,
    oracleKeypairPath: string,
    idlPath: string
  ) {
    this.connection = new Connection(rpcUrl, "confirmed");
    this.oracleKeypair = Keypair.fromSecretKey(
      Uint8Array.from(JSON.parse(fs.readFileSync(oracleKeypairPath, "utf-8")))
    );

    const wallet = new Wallet(this.oracleKeypair);
    this.provider = new AnchorProvider(this.connection, wallet, {
      commitment: "confirmed",
    });

    const idl = JSON.parse(fs.readFileSync(idlPath, "utf-8"));
    anchor.setProvider(this.provider);
    this.program = new Program(idl, this.provider);

    this.markets = new Map();

    console.log("DEBUG: Crank initialized");
    console.log("DEBUG: Oracle Authority:", this.oracleKeypair.publicKey.toString());
    console.log("DEBUG: Program ID:", programId);
  }

  addMarket(config: MarketConfig) {
    this.markets.set(config.marketSeed, config);
    console.log(`DEBUG: Added market to monitor: ${config.marketSeed}`);
    console.log(`DEBUG: Token: ${config.tokenMint}`);
    console.log(`DEBUG: Target: $${config.targetMarketCap / 1_000_000}`);
    console.log(`DEBUG: Deadline: ${new Date(config.deadline * 1000).toISOString()}`);
  }

  async fetchMarketCapFromDexScreener(tokenMint: string): Promise<MarketCapData | null> {
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

        console.log(`DEBUG: DexScreener data for ${tokenMint}:`);
        console.log(`  Market Cap: $${marketCap.toLocaleString()}`);
        console.log(`  Price: $${price}`);
        console.log(`  24h Volume: $${volume24h.toLocaleString()}`);

        return {
          marketCap,
          timestamp: Math.floor(Date.now() / 1000),
          price,
          volume24h,
        };
      }

      console.log(`DEBUG: No data found on DexScreener for ${tokenMint}`);
      return null;
    } catch (error) {
      console.error(`ERROR: Failed to fetch from DexScreener:`, error.message);
      return null;
    }
  }

  async fetchMarketCapFromBirdeye(tokenMint: string, apiKey: string): Promise<MarketCapData | null> {
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
        const marketCap = data.mc || 0;
        const price = data.price || 0;
        const volume24h = data.v24hUSD || 0;

        console.log(`DEBUG: Birdeye data for ${tokenMint}:`);
        console.log(`  Market Cap: $${marketCap.toLocaleString()}`);
        console.log(`  Price: $${price}`);
        console.log(`  24h Volume: $${volume24h.toLocaleString()}`);

        return {
          marketCap,
          timestamp: Math.floor(Date.now() / 1000),
          price,
          volume24h,
        };
      }

      console.log(`DEBUG: No data found on Birdeye for ${tokenMint}`);
      return null;
    } catch (error) {
      console.error(`ERROR: Failed to fetch from Birdeye:`, error.message);
      return null;
    }
  }

  async fetchMarketCap(tokenMint: string, birdeyeApiKey?: string): Promise<MarketCapData | null> {
    let data = await this.fetchMarketCapFromDexScreener(tokenMint);

    if (!data && birdeyeApiKey) {
      console.log("DEBUG: Trying Birdeye as fallback...");
      data = await this.fetchMarketCapFromBirdeye(tokenMint, birdeyeApiKey);
    }

    return data;
  }

  async checkAndResolveMarket(marketSeed: string, config: MarketConfig, birdeyeApiKey?: string) {
    try {
      const [marketPda] = PublicKey.findProgramAddressSync(
        [Buffer.from("market"), Buffer.from(marketSeed)],
        this.program.programId
      );

      const marketAccount = await this.program.account["Market"].fetch(marketPda);

      if (marketAccount.isResolved) {
        console.log(`DEBUG: Market ${marketSeed} already resolved`);
        return;
      }

      const currentTime = Math.floor(Date.now() / 1000);
      const deadlinePassed = currentTime >= config.deadline;

      console.log(`\nDEBUG: Checking market: ${marketSeed}`);
      console.log(`DEBUG: Current time: ${new Date(currentTime * 1000).toISOString()}`);
      console.log(`DEBUG: Deadline: ${new Date(config.deadline * 1000).toISOString()}`);
      console.log(`DEBUG: Deadline passed: ${deadlinePassed}`);

      const marketCapData = await this.fetchMarketCap(config.tokenMint, birdeyeApiKey);

      if (!marketCapData) {
        console.log("WARN: Could not fetch market cap data, skipping this check");
        return;
      }

      const currentMarketCapUsd = marketCapData.marketCap;
      const targetMarketCapUsd = config.targetMarketCap / 1_000_000;
      const targetReached = currentMarketCapUsd >= targetMarketCapUsd;

      console.log(`DEBUG: Current Market Cap: $${currentMarketCapUsd.toLocaleString()}`);
      console.log(`DEBUG: Target Market Cap: $${targetMarketCapUsd.toLocaleString()}`);
      console.log(`DEBUG: Target reached: ${targetReached}`);

      if (targetReached || deadlinePassed) {
        console.log(`\n🎯 RESOLVING MARKET: ${marketSeed}`);
        console.log(`Reason: ${targetReached ? "Target reached" : "Deadline passed"}`);

        await this.resolveMarket(
          marketSeed,
          Math.floor(currentMarketCapUsd * 1_000_000),
          marketCapData.timestamp
        );
      } else {
        console.log("DEBUG: Market not ready to resolve yet");
      }
    } catch (error) {
      console.error(`ERROR: Failed to check market ${marketSeed}:`, error);
    }
  }

  async resolveMarket(marketSeed: string, currentMarketCap: number, timestamp: number) {
    try {
      const [marketPda] = PublicKey.findProgramAddressSync(
        [Buffer.from("market"), Buffer.from(marketSeed)],
        this.program.programId
      );

      console.log("DEBUG: Sending resolution transaction...");
      console.log(`  Market PDA: ${marketPda.toString()}`);
      console.log(`  Current Market Cap: $${currentMarketCap / 1_000_000}`);
      console.log(`  Timestamp: ${timestamp}`);

      const tx = await this.program.methods
        .parimutuelResolveMarket(
          marketSeed,
          new anchor.BN(currentMarketCap),
          new anchor.BN(timestamp)
        )
        .accounts({
          market: marketPda,
          oracle: this.oracleKeypair.publicKey,
        })
        .signers([this.oracleKeypair])
        .rpc();

      console.log(`✅ Market resolved successfully!`);
      console.log(`Transaction: ${tx}`);
      console.log(`Explorer: https://solscan.io/tx/${tx}?cluster=devnet`);

      this.markets.delete(marketSeed);
      console.log(`DEBUG: Removed ${marketSeed} from monitoring list`);
    } catch (error) {
      console.error(`ERROR: Failed to resolve market:`, error);
      throw error;
    }
  }

  async startMonitoring(birdeyeApiKey?: string) {
    console.log("\n🚀 Starting market cap monitoring crank...\n");

    const checkMarkets = async () => {
      for (const [marketSeed, config] of this.markets.entries()) {
        await this.checkAndResolveMarket(marketSeed, config, birdeyeApiKey);
        await new Promise((resolve) => setTimeout(resolve, 2000));
      }
    };

    await checkMarkets();

    setInterval(async () => {
      if (this.markets.size > 0) {
        console.log(`\n⏰ Running scheduled check... (${new Date().toISOString()})`);
        await checkMarkets();
      } else {
        console.log("DEBUG: No markets to monitor");
      }
    }, 60000);

    console.log("DEBUG: Crank is running. Press Ctrl+C to stop.\n");
  }
}

async function main() {
  const RPC_URL = process.env.RPC_URL || "https://api.devnet.solana.com";
  const PROGRAM_ID = process.env.PROGRAM_ID || "MemeMarket1111111111111111111111111111111111";
  const ORACLE_KEYPAIR_PATH = process.env.ORACLE_KEYPAIR_PATH || path.join(__dirname, "../oracle-keypair.json");
  const IDL_PATH = process.env.IDL_PATH || path.join(__dirname, "../target/idl/mememarket.json");
  const BIRDEYE_API_KEY = process.env.BIRDEYE_API_KEY;

  console.log("=".repeat(80));
  console.log("PARIMUTUEL MARKET CAP CRANK");
  console.log("=".repeat(80));

  const crank = new MarketCapCrank(RPC_URL, PROGRAM_ID, ORACLE_KEYPAIR_PATH, IDL_PATH);

  const marketsConfig = JSON.parse(
    fs.readFileSync(process.env.MARKETS_CONFIG || "./markets-config.json", "utf-8")
  );

  for (const market of marketsConfig.markets) {
    crank.addMarket({
      marketSeed: market.marketSeed,
      tokenMint: market.tokenMint,
      targetMarketCap: market.targetMarketCap,
      deadline: market.deadline,
      checkIntervalMs: market.checkIntervalMs || 60000,
    });
  }

  await crank.startMonitoring(BIRDEYE_API_KEY);
}

if (require.main === module) {
  main().catch((error) => {
    console.error("FATAL ERROR:", error);
    process.exit(1);
  });
}

export { MarketCapCrank, MarketConfig, MarketCapData };
