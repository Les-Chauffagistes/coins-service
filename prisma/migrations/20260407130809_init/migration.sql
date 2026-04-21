-- CreateTable
CREATE TABLE "currency" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "name" TEXT NOT NULL,
    "description" TEXT,
    "claimRate" INTEGER NOT NULL,
    "claimLimit" INTEGER NOT NULL,

    CONSTRAINT "currency_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "wallet" (
    "currencyId" UUID NOT NULL,
    "userId" INTEGER NOT NULL,
    "balance" INTEGER NOT NULL DEFAULT 0,

    CONSTRAINT "wallet_pkey" PRIMARY KEY ("currencyId","userId")
);

-- CreateTable
CREATE TABLE "claims" (
    "currencyId" UUID NOT NULL,
    "userId" INTEGER NOT NULL,
    "lastClaimAt" TIMESTAMP(3),

    CONSTRAINT "claims_pkey" PRIMARY KEY ("currencyId","userId")
);

-- CreateTable
CREATE TABLE "log" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "userId" INTEGER NOT NULL,
    "currencyId" UUID NOT NULL,
    "amount" INTEGER NOT NULL,
    "date" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "reason" TEXT,
    "fromState" TEXT,
    "toState" TEXT,

    CONSTRAINT "log_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "currency_name_key" ON "currency"("name");

-- CreateIndex
CREATE INDEX "wallet_userId_idx" ON "wallet"("userId");

-- CreateIndex
CREATE INDEX "log_userId_currencyId_idx" ON "log"("userId", "currencyId");

-- AddForeignKey
ALTER TABLE "wallet" ADD CONSTRAINT "wallet_currencyId_fkey" FOREIGN KEY ("currencyId") REFERENCES "currency"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "claims" ADD CONSTRAINT "claims_currencyId_fkey" FOREIGN KEY ("currencyId") REFERENCES "currency"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "log" ADD CONSTRAINT "log_currencyId_fkey" FOREIGN KEY ("currencyId") REFERENCES "currency"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- Add constraint
ALTER TABLE "wallet" ADD CONSTRAINT balance_non_negative CHECK (balance >= 0);