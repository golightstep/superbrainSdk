import koffi from 'koffi';
import * as os from 'os';
import * as path from 'path';
import * as fs from 'fs';

export class SuperbrainError extends Error {
    constructor(message: string) {
        super(message);
        this.name = 'SuperbrainError';
    }
}

// Locate shared library
const libName = os.platform() === 'darwin' ? 'libsuperbrain.dylib' : 'libsuperbrain.so';

// Try finding it correctly in the package or local structure
let libPath = path.join(__dirname, '..', '..', 'lib', libName);
if (!fs.existsSync(libPath)) {
    libPath = path.join(process.cwd(), libName);
}
if (!fs.existsSync(libPath)) {
    libPath = path.join(process.cwd(), '..', 'lib', libName);
}

if (!fs.existsSync(libPath)) {
    throw new SuperbrainError(`Shared library ${libName} not found at ${libPath}. Ensure it is built and in the correct path.`);
}

const lib = koffi.load(libPath);

// C Bindings
const SB_NewClient = lib.func('SB_NewClient', 'str', ['str']);
const SB_NewClientWithEncryption = lib.func('SB_NewClientWithEncryption', 'str', ['str', 'uint8_t*', 'int']);
const SB_Register = lib.func('SB_Register', 'str', ['str', 'str']);
const SB_Allocate = lib.func('SB_Allocate', 'str', ['str', 'uint64_t']);
const SB_Write = lib.func('SB_Write', 'str', ['str', 'str', 'uint64_t', 'uint8_t*', 'uint64_t']);
const SB_Read = lib.func('SB_Read', 'str', ['str', 'str', 'uint64_t', 'uint64_t', '_Out_ uint8_t**', '_Out_ uint64_t*']);
const SB_Free = lib.func('SB_Free', 'str', ['str', 'str']);
const SB_GetPointer = lib.func('SB_GetPointer', 'str', ['str', 'str']);

const SB_WriteCognitive = lib.func('SB_WriteCognitive', 'str', ['str', 'str', 'uint64_t', 'uint8_t*', 'uint64_t', 'float', 'str', 'str', 'str']);
const SB_ResolveConflict = lib.func('SB_ResolveConflict', 'str', ['str', 'str', 'uint8_t*', 'uint64_t', 'str', '_Out_ uint8_t**', '_Out_ uint64_t*']);

export class Client {
    private clientId: string;

    constructor(addrs: string, encryptionKey?: Buffer) {
        let res: string;
        if (encryptionKey) {
            if (encryptionKey.length !== 32) {
                throw new SuperbrainError('Encryption key must be exactly 32 bytes for AES-GCM-256');
            }
            res = SB_NewClientWithEncryption(addrs, encryptionKey, encryptionKey.length);
        } else {
            res = SB_NewClient(addrs);
        }

        if (res && res.startsWith('error:')) {
            throw new SuperbrainError(res);
        }

        this.clientId = res;
    }

    public register(agentId: string): void {
        const res = SB_Register(this.clientId, agentId);
        if (res && res.startsWith('error:')) {
            throw new SuperbrainError(res);
        }
    }

    public allocate(size: number): string {
        const res = SB_Allocate(this.clientId, size);
        if (res && res.startsWith('error:')) {
            throw new SuperbrainError(res);
        }
        return res;
    }

    public writeCognitive(ptrId: string, offset: number, data: Buffer, liveliness: number, intent: string, summary: string, tag: string): void {
        const res = SB_WriteCognitive(this.clientId, ptrId, offset, data, data.length, liveliness, intent, summary, tag);
        if (res && res.startsWith('error:')) {
            throw new SuperbrainError(res);
        }
    }

    public read(ptrId: string, offset: number, length: number): Buffer {
        // Output pointers for koffi
        const outDataPtr = [null];
        const outLenPtr = [0];

        const res = SB_Read(this.clientId, ptrId, offset, length, outDataPtr, outLenPtr);

        if (res && res.startsWith('error:')) {
            throw new SuperbrainError(res);
        }

        const outBufPtr = outDataPtr[0] as any;
        const outLen = outLenPtr[0] as number;

        if (!outBufPtr || outLen === 0) {
            return Buffer.alloc(0);
        }

        // Decode the C string memory pointer into a Buffer
        const decodedBuffer = koffi.decode(outBufPtr, 'uint8_t', outLen);
        const buffer = Buffer.from(decodedBuffer);

        // Note: C-allocated pointer memory leak if we don't C-free, 
        // but for now Superbrain handles general lifecycle cleanup 
        // when client exists or pointer freed.

        return buffer;
    }

    public resolveConflict(ptrId: string, newData: Buffer, intent: string): Buffer {
        const outDataPtr = [null];
        const outLenPtr = [0];

        const res = SB_ResolveConflict(this.clientId, ptrId, newData, newData.length, intent, outDataPtr, outLenPtr);

        if (res && res.startsWith('error:')) {
            throw new SuperbrainError(res);
        }

        const outBufPtr = outDataPtr[0] as any;
        const outLen = outLenPtr[0] as number;

        if (!outBufPtr || outLen === 0) {
            return Buffer.alloc(0);
        }

        const decodedBuffer = koffi.decode(outBufPtr, 'uint8_t', outLen);
        return Buffer.from(decodedBuffer);
    }

    public free(ptrId: string): void {
        const res = SB_Free(this.clientId, ptrId);
        if (res && res.startsWith('error:')) {
            throw new SuperbrainError(res);
        }
    }

    public attach(ptrId: string): void {
        const res = SB_GetPointer(this.clientId, ptrId);
        if (res && res.startsWith('error:')) {
            throw new SuperbrainError(res);
        }
    }
}
