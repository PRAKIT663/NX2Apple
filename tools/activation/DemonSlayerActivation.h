// Included by the pinned iOS engine's main.m for the Demon Slayer 2 IPA.
#include <stdlib.h>

@interface DemonSlayerActivation : UIViewController
@property (nonatomic, copy) void (^onAllowed)(void);
@end

@implementation DemonSlayerActivation {
    UITextField *_code;
    UILabel *_status;
    UIButton *_submit;
    NSString *_installation;
}

- (void)viewDidLoad {
    [super viewDidLoad];
    self.view.backgroundColor = UIColor.systemBackgroundColor;

    _status = [UILabel new];
    _status.numberOfLines = 0;
    _status.textAlignment = NSTextAlignmentCenter;

    _code = [UITextField new];
    _code.placeholder = @"Activation code";
    _code.borderStyle = UITextBorderStyleRoundedRect;
    _code.autocapitalizationType = UITextAutocapitalizationTypeNone;
    _code.autocorrectionType = UITextAutocorrectionTypeNo;
    _code.spellCheckingType = UITextSpellCheckingTypeNo;
    _code.secureTextEntry = YES;
    _code.returnKeyType = UIReturnKeyGo;
    [_code addTarget:self action:@selector(submit) forControlEvents:UIControlEventEditingDidEndOnExit];
    _code.hidden = YES;

    _submit = [UIButton buttonWithType:UIButtonTypeSystem];
    [_submit addTarget:self action:@selector(submit) forControlEvents:UIControlEventTouchUpInside];
    [_submit setTitle:@"Retry" forState:UIControlStateNormal];
    _submit.enabled = NO;

    UIStackView *stack = [[UIStackView alloc] initWithArrangedSubviews:@[_status, _code, _submit]];
    stack.axis = UILayoutConstraintAxisVertical;
    stack.spacing = 12;
    stack.translatesAutoresizingMaskIntoConstraints = NO;
    [self.view addSubview:stack];

    UILayoutGuide *safe = self.view.safeAreaLayoutGuide;
    NSLayoutConstraint *preferredWidth = [stack.widthAnchor constraintEqualToConstant:360];
    preferredWidth.priority = UILayoutPriorityDefaultHigh;
    [NSLayoutConstraint activateConstraints:@[
        preferredWidth,
        [stack.centerXAnchor constraintEqualToAnchor:safe.centerXAnchor],
        [stack.centerYAnchor constraintEqualToAnchor:safe.centerYAnchor],
        [stack.leadingAnchor constraintGreaterThanOrEqualToAnchor:safe.leadingAnchor constant:20],
        [stack.trailingAnchor constraintLessThanOrEqualToAnchor:safe.trailingAnchor constant:-20],
    ]];
    [self submit];
}

- (NSString *)loadInstallation {
    NSFileManager *files = NSFileManager.defaultManager;
    NSURL *support = [files URLsForDirectory:NSApplicationSupportDirectory inDomains:NSUserDomainMask].firstObject;
    NSURL *directory = [support URLByAppendingPathComponent:@"Activation" isDirectory:YES];
    if (!directory ||
        ![files createDirectoryAtURL:directory withIntermediateDirectories:YES attributes:nil error:NULL] ||
        ![directory setResourceValue:@YES forKey:NSURLIsExcludedFromBackupKey error:NULL]) return nil;

    NSURL *file = [directory URLByAppendingPathComponent:@"installation"];
    NSError *error = nil;
    NSData *data = [NSData dataWithContentsOfURL:file options:0 error:&error];
    if (!data && [error.domain isEqualToString:NSCocoaErrorDomain] && error.code == NSFileReadNoSuchFileError) {
        uint8_t bytes[32];
        arc4random_buf(bytes, sizeof(bytes));
        data = [NSData dataWithBytes:bytes length:sizeof(bytes)];
        if (![data writeToURL:file options:NSDataWritingAtomic error:NULL]) return nil;
    }
    if (data.length != 32) return nil;

    NSMutableString *token = [NSMutableString stringWithCapacity:64];
    const uint8_t *bytes = data.bytes;
    for (NSUInteger i = 0; i < data.length; i++) [token appendFormat:@"%02x", (unsigned int)bytes[i]];
    return token;
}

- (void)submit {
    [self.view endEditing:YES];
    NSString *code = _code.hidden ? nil : [[_code.text stringByTrimmingCharactersInSet:
        NSCharacterSet.whitespaceAndNewlineCharacterSet] lowercaseString];
    if (code && (code.length != 36 || [code rangeOfCharacterFromSet:
        [[NSCharacterSet characterSetWithCharactersInString:@"0123456789abcdef"] invertedSet]].location != NSNotFound)) {
        _status.text = @"Enter the 36-character activation code.";
        return;
    }
    _installation = _installation ?: [self loadInstallation];
    if (!_installation) {
        _status.text = @"Could not load this installation’s activation data. Try again.";
        _submit.enabled = YES;
        return;
    }

    _status.text = @"Checking access…";
    _submit.enabled = NO;
    _code.enabled = NO;
    NSURL *base = [NSURL URLWithString:@"https://dragon-ball-activation.fcprakit02443.workers.dev"];
    NSURL *url = [base URLByAppendingPathComponent:code ? @"redeem" : @"check"];
    NSMutableURLRequest *request = [NSMutableURLRequest requestWithURL:url];
    request.timeoutInterval = 15;
    request.HTTPMethod = @"POST";
    [request setValue:@"application/json" forHTTPHeaderField:@"Content-Type"];
    NSMutableDictionary *body = [@{
        @"game": @"demon-slayer-2",
        @"installationToken": _installation,
    } mutableCopy];
    if (code) body[@"activationCode"] = code;
    request.HTTPBody = [NSJSONSerialization dataWithJSONObject:body options:0 error:NULL];

    [[[NSURLSession sharedSession] dataTaskWithRequest:request completionHandler:
        ^(NSData *data, NSURLResponse *response, NSError *error) {
        NSInteger status = [response isKindOfClass:NSHTTPURLResponse.class] ?
            ((NSHTTPURLResponse *)response).statusCode : 0;
        id payload = data ? [NSJSONSerialization JSONObjectWithData:data options:0 error:NULL] : nil;
        id allowed = [payload isKindOfClass:NSDictionary.class] ? payload[@"allowed"] : nil;
        dispatch_async(dispatch_get_main_queue(), ^{
            if (!error && status == 200 && [allowed isEqual:@YES]) {
                if (self.onAllowed) self.onAllowed();
                return;
            }
            if (!error && status == (code ? 403 : 200) && [allowed isEqual:@NO]) {
                self->_code.hidden = NO;
                [self->_submit setTitle:@"Activate" forState:UIControlStateNormal];
                self->_status.text = code ? @"This code could not activate this installation." :
                    @"Enter your activation code to play.";
            } else {
                self->_status.text = @"Could not verify access. Check your connection and try again.";
            }
            self->_code.enabled = YES;
            self->_submit.enabled = YES;
        });
    }] resume];
}
@end
