/**
 * Program IDL in camelCase format in order to be used in JS/TS.
 *
 * Note that this is only a type helper and is not the actual IDL. The original
 * IDL can be found at `target/idl/mememarket.json`.
 */
export type Mememarket = {
  "address": "GYDiDN3Snsff7ZJDqmSXyJciWZX4aXGqnLbTsSjXpPgB",
  "metadata": {
    "name": "mememarket",
    "version": "0.1.0",
    "spec": "0.1.0",
    "description": "MemeMarket Protocol"
  },
  "instructions": [
    {
      "name": "parimutuelClaimReward",
      "docs": [
        "Claim reward after market resolution"
      ],
      "discriminator": [
        2,
        227,
        141,
        35,
        207,
        201,
        29,
        156
      ],
      "accounts": [
        {
          "name": "market",
          "writable": true,
          "pda": {
            "seeds": [
              {
                "kind": "const",
                "value": [
                  109,
                  97,
                  114,
                  107,
                  101,
                  116
                ]
              },
              {
                "kind": "arg",
                "path": "marketSeed"
              }
            ]
          }
        },
        {
          "name": "userBet",
          "writable": true,
          "pda": {
            "seeds": [
              {
                "kind": "const",
                "value": [
                  117,
                  115,
                  101,
                  114,
                  95,
                  98,
                  101,
                  116
                ]
              },
              {
                "kind": "account",
                "path": "market"
              },
              {
                "kind": "account",
                "path": "user"
              }
            ]
          }
        },
        {
          "name": "escrow",
          "writable": true,
          "pda": {
            "seeds": [
              {
                "kind": "const",
                "value": [
                  101,
                  115,
                  99,
                  114,
                  111,
                  119
                ]
              },
              {
                "kind": "account",
                "path": "market"
              }
            ]
          }
        },
        {
          "name": "user",
          "writable": true,
          "signer": true
        },
        {
          "name": "systemProgram",
          "address": "11111111111111111111111111111111"
        }
      ],
      "args": [
        {
          "name": "marketSeed",
          "type": "string"
        }
      ]
    },
    {
      "name": "parimutuelInitializeMarket",
      "docs": [
        "Initialize a new parimutuel market",
        "Charges 0.015 SOL creation fee to treasury"
      ],
      "discriminator": [
        35,
        5,
        80,
        5,
        54,
        91,
        94,
        151
      ],
      "accounts": [
        {
          "name": "market",
          "writable": true,
          "pda": {
            "seeds": [
              {
                "kind": "const",
                "value": [
                  109,
                  97,
                  114,
                  107,
                  101,
                  116
                ]
              },
              {
                "kind": "arg",
                "path": "marketSeed"
              }
            ]
          }
        },
        {
          "name": "treasury",
          "writable": true
        },
        {
          "name": "creator",
          "writable": true,
          "signer": true
        },
        {
          "name": "systemProgram",
          "address": "11111111111111111111111111111111"
        }
      ],
      "args": [
        {
          "name": "marketSeed",
          "type": "string"
        },
        {
          "name": "oracleAuthority",
          "type": "pubkey"
        },
        {
          "name": "tokenMint",
          "type": "pubkey"
        },
        {
          "name": "targetMarketCap",
          "type": "u64"
        },
        {
          "name": "deadline",
          "type": "i64"
        }
      ]
    },
    {
      "name": "parimutuelPlaceBet",
      "docs": [
        "Place a bet on YES or NO"
      ],
      "discriminator": [
        132,
        33,
        88,
        153,
        31,
        54,
        117,
        99
      ],
      "accounts": [
        {
          "name": "market",
          "writable": true,
          "pda": {
            "seeds": [
              {
                "kind": "const",
                "value": [
                  109,
                  97,
                  114,
                  107,
                  101,
                  116
                ]
              },
              {
                "kind": "arg",
                "path": "marketSeed"
              }
            ]
          }
        },
        {
          "name": "userBet",
          "writable": true,
          "pda": {
            "seeds": [
              {
                "kind": "const",
                "value": [
                  117,
                  115,
                  101,
                  114,
                  95,
                  98,
                  101,
                  116
                ]
              },
              {
                "kind": "account",
                "path": "market"
              },
              {
                "kind": "account",
                "path": "user"
              }
            ]
          }
        },
        {
          "name": "escrow",
          "writable": true,
          "pda": {
            "seeds": [
              {
                "kind": "const",
                "value": [
                  101,
                  115,
                  99,
                  114,
                  111,
                  119
                ]
              },
              {
                "kind": "account",
                "path": "market"
              }
            ]
          }
        },
        {
          "name": "user",
          "writable": true,
          "signer": true
        },
        {
          "name": "systemProgram",
          "address": "11111111111111111111111111111111"
        }
      ],
      "args": [
        {
          "name": "marketSeed",
          "type": "string"
        },
        {
          "name": "amount",
          "type": "u64"
        },
        {
          "name": "side",
          "type": "bool"
        }
      ]
    },
    {
      "name": "parimutuelResolveMarket",
      "docs": [
        "Resolve market (oracle only)"
      ],
      "discriminator": [
        158,
        152,
        188,
        226,
        176,
        69,
        69,
        16
      ],
      "accounts": [
        {
          "name": "market",
          "writable": true,
          "pda": {
            "seeds": [
              {
                "kind": "const",
                "value": [
                  109,
                  97,
                  114,
                  107,
                  101,
                  116
                ]
              },
              {
                "kind": "arg",
                "path": "marketSeed"
              }
            ]
          }
        },
        {
          "name": "oracle",
          "signer": true
        }
      ],
      "args": [
        {
          "name": "marketSeed",
          "type": "string"
        },
        {
          "name": "currentMarketCap",
          "type": "u64"
        },
        {
          "name": "timestamp",
          "type": "i64"
        }
      ]
    }
  ],
  "accounts": [
    {
      "name": "market",
      "discriminator": [
        219,
        190,
        213,
        55,
        0,
        227,
        198,
        154
      ]
    },
    {
      "name": "userBet",
      "discriminator": [
        180,
        131,
        8,
        241,
        60,
        243,
        46,
        63
      ]
    }
  ],
  "errors": [
    {
      "code": 6000,
      "name": "unauthorized",
      "msg": "Unauthorized: Only admin can perform this action"
    },
    {
      "code": 6001,
      "name": "marketResolved",
      "msg": "Market has already been resolved"
    },
    {
      "code": 6002,
      "name": "marketAlreadyResolved",
      "msg": "Market has already been resolved"
    },
    {
      "code": 6003,
      "name": "marketNotResolved",
      "msg": "Market has not been resolved yet"
    },
    {
      "code": 6004,
      "name": "invalidAmount",
      "msg": "Invalid amount: Must be greater than zero"
    },
    {
      "code": 6005,
      "name": "alreadyClaimed",
      "msg": "Reward already claimed"
    },
    {
      "code": 6006,
      "name": "notWinner",
      "msg": "User is not on the winning side"
    },
    {
      "code": 6007,
      "name": "noWinner",
      "msg": "No winner set for this market"
    },
    {
      "code": 6008,
      "name": "emptyPool",
      "msg": "Winning pool is empty"
    },
    {
      "code": 6009,
      "name": "overflow",
      "msg": "Arithmetic overflow occurred"
    },
    {
      "code": 6010,
      "name": "divisionByZero",
      "msg": "Division by zero"
    },
    {
      "code": 6011,
      "name": "invalidMarket",
      "msg": "Invalid market"
    },
    {
      "code": 6012,
      "name": "invalidDeadline",
      "msg": "Invalid deadline: Must be in the future"
    },
    {
      "code": 6013,
      "name": "deadlinePassed",
      "msg": "Deadline has passed: Cannot place bets"
    },
    {
      "code": 6014,
      "name": "staleData",
      "msg": "Oracle data is stale: Timestamp too old"
    },
    {
      "code": 6015,
      "name": "cannotResolveYet",
      "msg": "Cannot resolve yet: Target not reached and deadline not passed"
    },
    {
      "code": 6016,
      "name": "insufficientFunds",
      "msg": "Insufficient funds: Need 0.015 SOL + rent for market creation"
    }
  ],
  "types": [
    {
      "name": "market",
      "docs": [
        "Parimutuel betting market account structure with automated oracle resolution",
        "Debug: Stores pools, target market cap, deadline, and oracle data"
      ],
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "creator",
            "type": "pubkey"
          },
          {
            "name": "oracleAuthority",
            "type": "pubkey"
          },
          {
            "name": "tokenMint",
            "type": "pubkey"
          },
          {
            "name": "totalYesPool",
            "type": "u64"
          },
          {
            "name": "totalNoPool",
            "type": "u64"
          },
          {
            "name": "targetMarketCap",
            "type": "u64"
          },
          {
            "name": "deadline",
            "type": "i64"
          },
          {
            "name": "isResolved",
            "type": "bool"
          },
          {
            "name": "winner",
            "type": {
              "option": "bool"
            }
          },
          {
            "name": "targetReached",
            "type": "bool"
          },
          {
            "name": "resolvedAt",
            "type": "i64"
          },
          {
            "name": "bump",
            "type": "u8"
          }
        ]
      }
    },
    {
      "name": "userBet",
      "docs": [
        "User bet account structure",
        "Debug: Tracks individual user's bet amount, side, and claim status"
      ],
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "user",
            "type": "pubkey"
          },
          {
            "name": "market",
            "type": "pubkey"
          },
          {
            "name": "amount",
            "type": "u64"
          },
          {
            "name": "side",
            "type": "bool"
          },
          {
            "name": "claimed",
            "type": "bool"
          }
        ]
      }
    }
  ]
};
