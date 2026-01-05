const { Keypair } = require("@solana/web3.js");
const fs = require("fs");
const path = require("path");

console.log("🔧 Setting up Oracle Crank...\n");

// Generate oracle keypair
console.log("1. Generating oracle keypair...");
const oracleKeypair = Keypair.generate();
const secretKey = Array.from(oracleKeypair.secretKey);

// Save to file
fs.writeFileSync(
  path.join(__dirname, "oracle-keypair.json"),
  JSON.stringify(secretKey)
);

console.log("✅ Oracle keypair generated!");
console.log("   Public Key:", oracleKeypair.publicKey.toString());
console.log("   Saved to: oracle-keypair.json\n");

// Update .env file with actual program ID if needed
console.log("2. Configuration files:");
console.log("   ✅ .env - Already configured");
console.log("   ✅ markets-config.json - Ready to customize\n");

console.log("📝 Next Steps:");
console.log("   1. Fund the oracle wallet with SOL for transaction fees:");
console.log(`      solana airdrop 1 ${oracleKeypair.publicKey.toString()} --url devnet`);
console.log("      (Or transfer SOL manually)\n");
console.log("   2. Update markets-config.json with your market details\n");
console.log("   3. Build your Anchor program:");
console.log("      cd .. && anchor build\n");
console.log("   4. Deploy your program:");
console.log("      anchor deploy --provider.cluster devnet\n");
console.log("   5. Update PROGRAM_ID in .env with deployed program ID\n");
console.log("   6. Start the crank:");
console.log("      npm start\n");

console.log("🎯 Oracle Authority for market creation:");
console.log(`   ${oracleKeypair.publicKey.toString()}\n`);
console.log("   Use this public key when creating markets!\n");
